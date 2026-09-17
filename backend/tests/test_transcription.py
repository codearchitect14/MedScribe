"""Integration test for the batch audio transcription path (faster-whisper).

Uses a short synthetically generated WAV file (a pure tone, not real speech)
so this test runs without any external audio sample and without a network
call at test time beyond the model weights faster-whisper downloads on
first use. It verifies the pipeline runs end to end (file in, transcript
text out, no crash) rather than transcription accuracy, which requires real
speech audio.
"""

import math
import struct
import wave
from pathlib import Path

import pytest

from app.services.clinical.transcription import transcribe_audio_file


def _write_tone_wav(path: Path, *, duration_seconds: float = 1.5, freq_hz: float = 440.0) -> None:
    framerate = 16000
    n_frames = int(duration_seconds * framerate)
    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        frames = bytearray()
        for i in range(n_frames):
            sample = int(3000 * math.sin(2 * math.pi * freq_hz * (i / framerate)))
            frames += struct.pack("<h", sample)
        wav_file.writeframes(bytes(frames))


@pytest.mark.slow
def test_transcribe_audio_file_runs_without_error(tmp_path):
    wav_path = tmp_path / "tone.wav"
    _write_tone_wav(wav_path)

    result = transcribe_audio_file(str(wav_path))

    assert isinstance(result, str)
