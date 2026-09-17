"""Live, streaming audio transcription over a WebSocket (plan.md Phase 5).

Protocol (see docs/live-transcription.md for the full write-up):

Client -> server:
  - Binary frames: raw 16-bit PCM, mono, LIVE_SAMPLE_RATE_HZ audio chunks.
  - Text frames: JSON control messages, currently {"type": "stop"}.

Server -> client, JSON text frames:
  - {"type": "queued"}                          worker pool full, waiting for a slot
  - {"type": "ready"}                            a worker slot was acquired, start streaming audio
  - {"type": "partial", "seq": N, "text": "..."} unconfirmed, overwrites the previous partial
  - {"type": "final", "seq": N, "text": "..."}   stable segment, appended to raw_transcript
  - {"type": "stopped", "raw_transcript": "..."} sent once, just before the server closes the socket
  - {"type": "error", "detail": "..."}

Concurrency: at most `live_worker_pool_size` sessions run Whisper inference
at once, for the lifetime of the session (not per chunk), so one long
encounter cannot starve other requests and additional sessions queue rather
than drop audio.
"""

import asyncio
from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.services.clinical.transcription import get_whisper_model

BYTES_PER_SAMPLE = 2  # 16-bit PCM


@lru_cache
def get_worker_pool_semaphore() -> asyncio.Semaphore:
    settings = get_settings()
    return asyncio.Semaphore(settings.live_worker_pool_size)


def _pcm16_bytes_to_float32(chunk: bytes) -> np.ndarray:
    return np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0


async def transcribe_segment(pcm_bytes: bytes) -> str:
    """Runs one Whisper inference pass over the given PCM16 buffer.

    Blocking (CPU-bound) work is pushed to a thread so the event loop stays
    responsive for other WebSocket sessions and HTTP requests.
    """
    if not pcm_bytes:
        return ""
    audio = _pcm16_bytes_to_float32(pcm_bytes)
    model = get_whisper_model()

    def _run() -> str:
        # beam_size=1 (greedy) rather than the batch path's 5: live
        # transcription favors low latency and lower peak memory over the
        # small accuracy gain from beam search, since each segment is
        # re-transcribed repeatedly as more audio arrives.
        segments, _info = model.transcribe(audio, beam_size=1)
        return " ".join(s.text.strip() for s in segments).strip()

    return await asyncio.to_thread(_run)


class LiveTranscriptionSession:
    """Buffers incoming PCM audio for one encounter and decides when to run
    a partial vs. a final transcription pass, per plan.md Phase 5's
    sliding-window description. "Stable sentence boundary" is approximated
    with a fixed time window rather than real voice-activity detection.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._sample_rate = settings.live_sample_rate_hz
        self._partial_interval = settings.live_partial_interval_seconds
        self._finalize_after = settings.live_finalize_after_seconds
        self._max_segment = settings.live_max_segment_seconds

        self._buffer = bytearray()
        self._duration_at_last_partial = 0.0
        self.sequence = 0
        self.paused = False

    def _buffer_duration_seconds(self) -> float:
        return len(self._buffer) / (self._sample_rate * BYTES_PER_SAMPLE)

    def add_chunk(self, chunk: bytes) -> None:
        if not self.paused:
            self._buffer.extend(chunk)

    def should_run_partial(self) -> bool:
        duration = self._buffer_duration_seconds()
        return duration > 0 and (duration - self._duration_at_last_partial) >= self._partial_interval

    def should_finalize(self) -> bool:
        return self._buffer_duration_seconds() >= self._finalize_after

    def is_over_hard_cap(self) -> bool:
        return self._buffer_duration_seconds() >= self._max_segment

    def mark_partial_run(self) -> None:
        self._duration_at_last_partial = self._buffer_duration_seconds()

    def snapshot_buffer(self) -> bytes:
        return bytes(self._buffer)

    def reset_after_finalize(self) -> None:
        self._buffer = bytearray()
        self._duration_at_last_partial = 0.0

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def has_pending_audio(self) -> bool:
        return self._buffer_duration_seconds() > 0.3
