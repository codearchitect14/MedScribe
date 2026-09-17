# Live Transcription

Phase 5 adds a third transcript ingestion path alongside pasted text (Phase 4) and uploaded audio files (Phase 4): live, in-browser recording streamed to the backend over a WebSocket and transcribed in near real time with the same self-hosted faster-whisper model used for batch transcription.

This phase is backend-only. The frontend component that drives this protocol (start/pause/resume/stop controls, rendering partial vs. final text) is built in Phase 8; this document specifies the protocol that component talks to.

## Starting a live encounter

1. `POST /encounters/live` with `{"patient_id": "..."}` creates an encounter with `status = recording` and an empty transcript, and returns its id. Only `clinician`, `admin`, and `super_admin` may call this (same roles as the other encounter-creation endpoints).
2. Open a WebSocket to `/ws/encounters/{encounter_id}/live-transcribe?token=<access_token>`. Browsers cannot set custom headers on a WebSocket handshake, so the JWT access token is passed as a query parameter rather than an `Authorization` header.
3. The server validates the token, confirms the encounter belongs to the caller's organization (and, for a clinician, that it is their own encounter), and confirms the encounter is currently `recording`. Any failure closes the socket immediately with a 4401 (unauthorized), 4404 (not found), or 4409 (wrong state) close code.

## Worker pool and the `queued`/`ready` handshake

At most `LIVE_WORKER_POOL_SIZE` (default 2) live sessions run Whisper inference at once, for the lifetime of the session, not per chunk — this is what "sized to the host's CPU cores" means in practice here: one slot per session for as long as it stays connected. If the pool is full when a new session connects, the server immediately sends `{"type": "queued"}` and waits for a slot to free up, rather than dropping the connection or discarding audio.

The client must wait for `{"type": "ready"}` before it starts sending audio chunks. Sending audio before `ready` is undefined (the server has not started its receive loop yet in the queued case).

## Audio format

Binary WebSocket frames must be raw 16-bit signed little-endian PCM, mono, at `LIVE_SAMPLE_RATE_HZ` (default 16000, matching Whisper's expected input rate). Use the browser's AudioWorklet API (not MediaRecorder, which produces compressed container formats) to capture and resample microphone audio to this format before sending each chunk. Sending roughly one to two seconds of audio per chunk is a reasonable default; the server does not care about the chunk size itself, only the cumulative buffered duration.

## Partial vs. final segments

The server buffers incoming audio into a growing segment and decides when to run inference and what kind of message to emit:

- **Partial**: once at least `LIVE_PARTIAL_INTERVAL_SECONDS` (default 1.5s) of new audio has accumulated since the last partial, the server runs Whisper over the whole current segment and sends `{"type": "partial", "seq": N, "text": "..."}`. Each partial replaces the previous one in the UI; it is not appended to the transcript yet.
- **Final**: once the segment reaches `LIVE_FINALIZE_AFTER_SECONDS` (default 8s), the server treats it as stable, runs one more inference pass, appends the result to the encounter's `raw_transcript`, checkpoints it to the database immediately, resets the segment buffer, and sends `{"type": "final", "seq": N, "text": "..."}`.
- **Hard cap**: `LIVE_MAX_SEGMENT_SECONDS` (default 20s) force-finalizes a segment even if the soft threshold above was somehow missed, as a safety bound on memory and latency.

This is a fixed-time-window approximation of "a stable sentence boundary," not real voice-activity detection or silence-based endpointing. A production system aiming for tighter segment boundaries would add VAD; that is out of scope for this reference build.

Every message the server sends carries a strictly increasing `seq` number (partials and finals share one counter), so the client can detect drops or reordering.

## Checkpointing and reconnection

Every finalized segment is committed to the database immediately (the `_finalize_pending` step: `session.commit()` right after appending to `raw_transcript`), so at most `LIVE_FINALIZE_AFTER_SECONDS` of audio is ever at risk if the connection drops uncleanly. `raw_transcript` is always appended to, never overwritten, so if the client reconnects to the same `encounter_id` (still in `recording` status), it resumes with a fresh, empty segment buffer and its new finalized segments are appended after whatever was already saved. No special "resume" message is needed; the reconnect is just a new WebSocket connection to the same URL.

## Stopping

The client sends `{"type": "stop"}` as a text frame. The server finalizes any pending (not-yet-finalized) audio in the current segment, sets the encounter's status to `transcribed`, sends `{"type": "stopped", "raw_transcript": "<the full transcript>"}`, and closes the socket. From this point the encounter behaves exactly like one created via the Phase 4 text or file-upload paths: `POST /encounters/{id}/soap-note` works immediately, with no separate "convert to encounter" step. This is what "no additional manual step required" means in the plan.

If the final Whisper pass during stop fails (see below), the server still transitions the encounter to `transcribed` and closes cleanly; it sends `{"type": "error", ...}` first so the client knows that last segment did not make it in.

## Pause and resume

`{"type": "pause"}` and `{"type": "resume"}` text frames toggle whether incoming audio chunks are added to the buffer. The server keeps accepting frames while paused; it just discards the audio rather than buffering it, so resuming does not produce a burst of stale audio.

## Error handling

A transcription failure on a single segment (model error, malformed audio, out-of-memory) is caught, logged, and reported to the client as `{"type": "error", "detail": "..."}`; the session keeps running rather than dropping the connection. The same applies to the final segment processed during `stop`. The only conditions that close the socket outright are the initial auth/authorization/state checks and an explicit `stop`.

## Resource sizing and the file-based fallback

Live transcription's only real cost is server CPU (no per-minute billing, since Whisper is self-hosted), so `LIVE_WORKER_POOL_SIZE` is the main lever: benchmark how many concurrent `small`/`base`-sized Whisper sessions your actual deployment target can sustain before setting it, per plan.md Phase 5. If live streaming CPU load is not practical for a given deployment, set `LIVE_TRANSCRIPTION_ENABLED=false`; the WebSocket route then closes immediately with code 1013 on every connection attempt, and the client should fall back to recording locally in the browser and uploading the completed file to `POST /encounters/audio` (the Phase 4 batch path), which produces an equivalent `transcribed`-status encounter.
