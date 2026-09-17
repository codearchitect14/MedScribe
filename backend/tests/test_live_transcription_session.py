"""Pure unit tests for the live-transcription buffering/cadence logic
(no network, no model, no DB): app/services/clinical/live_transcription.py's
LiveTranscriptionSession decides when to run a partial vs. a final pass.
"""

from app.services.clinical.live_transcription import LiveTranscriptionSession

SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


def _silence_chunk(seconds: float) -> bytes:
    return b"\x00\x00" * int(seconds * SAMPLE_RATE)


def test_no_partial_before_interval_elapsed():
    session = LiveTranscriptionSession()
    session.add_chunk(_silence_chunk(0.5))
    assert session.should_run_partial() is False


def test_partial_triggers_after_interval():
    session = LiveTranscriptionSession()
    session.add_chunk(_silence_chunk(2.0))  # default interval is 1.5s
    assert session.should_run_partial() is True


def test_finalize_triggers_after_threshold():
    session = LiveTranscriptionSession()
    session.add_chunk(_silence_chunk(9.0))  # default finalize threshold is 8.0s
    assert session.should_finalize() is True


def test_hard_cap_forces_finalize_even_if_below_soft_threshold():
    session = LiveTranscriptionSession()
    session._finalize_after = 100.0  # simulate a misconfigured/very high soft threshold
    session.add_chunk(_silence_chunk(21.0))  # default hard cap is 20.0s
    assert session.should_finalize() is False
    assert session.is_over_hard_cap() is True


def test_reset_after_finalize_clears_buffer_and_partial_marker():
    session = LiveTranscriptionSession()
    session.add_chunk(_silence_chunk(9.0))
    session.mark_partial_run()
    session.reset_after_finalize()
    assert session.has_pending_audio() is False
    assert session.should_run_partial() is False


def test_paused_session_drops_incoming_audio():
    session = LiveTranscriptionSession()
    session.paused = True
    session.add_chunk(_silence_chunk(5.0))
    assert session.has_pending_audio() is False


def test_sequence_numbers_increment_monotonically():
    session = LiveTranscriptionSession()
    assert session.next_sequence() == 1
    assert session.next_sequence() == 2
    assert session.next_sequence() == 3


def test_has_pending_audio_ignores_trivially_short_buffers():
    session = LiveTranscriptionSession()
    session.add_chunk(_silence_chunk(0.1))
    assert session.has_pending_audio() is False
    session.add_chunk(_silence_chunk(0.5))
    assert session.has_pending_audio() is True
