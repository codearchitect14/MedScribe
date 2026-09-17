"""Self-hosted batch audio transcription via faster-whisper.

Used for the "upload a completed audio file" ingestion path (plan.md Phase
4). The live in-browser recording path added in Phase 5 reuses the same
model, loaded once at process startup, in a streaming configuration.
"""

from functools import lru_cache

from faster_whisper import WhisperModel

from app.core.config import get_settings


@lru_cache
def get_whisper_model() -> WhisperModel:
    settings = get_settings()
    return WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        # Keep peak memory low: this process may also hold a loaded
        # sentence-transformers/torch model at the same time (see
        # app/embeddings/embedder.py), and both compete for the same
        # MKL-backed thread pool on constrained hosts.
        cpu_threads=1,
    )


def transcribe_audio_file(file_path: str) -> str:
    """Runs a single batch transcription pass over a completed audio file.

    Returns the concatenated transcript text, with no speaker labels (the
    source is a single-channel recording; speaker attribution is left to
    the transcript cleaning/LLM stage downstream).
    """
    model = get_whisper_model()
    segments, _info = model.transcribe(file_path, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()
