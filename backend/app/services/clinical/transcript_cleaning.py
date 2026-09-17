"""Basic transcript cleaning applied before any transcript reaches the LLM
stage, regardless of whether it arrived as pasted text or as a transcribed
audio file (per plan.md Phase 4).
"""

import re

FILLER_WORDS = {"um", "uh", "erm", "uhh", "umm", "you know", "like,"}

_SPEAKER_LABEL_RE = re.compile(r"^\s*(doctor|dr\.?|physician|clinician|patient|pt\.?)\s*:\s*", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t]+")


def _normalize_speaker_label(line: str) -> str:
    match = _SPEAKER_LABEL_RE.match(line)
    if not match:
        return line
    label = match.group(1).lower()
    if label.startswith("doc") or label.startswith("dr") or label.startswith("phys") or label.startswith("clin"):
        normalized = "Doctor"
    else:
        normalized = "Patient"
    return f"{normalized}: {line[match.end():]}"


def _remove_filler_words(text: str) -> str:
    words = text.split(" ")
    kept = [w for w in words if w.strip(",.").lower() not in FILLER_WORDS]
    return " ".join(kept)


def clean_transcript(raw_transcript: str) -> str:
    lines = raw_transcript.strip().splitlines()
    cleaned_lines = []
    for line in lines:
        line = _normalize_speaker_label(line)
        line = _remove_filler_words(line)
        line = _WHITESPACE_RE.sub(" ", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)
