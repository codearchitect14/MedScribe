# Dependency Security Audit (Phase 9)

`pip-audit` (backend) and `npm audit` (frontend), run against the exact pinned versions in `backend/pyproject.toml` and `frontend/package.json`. Every finding below was either resolved by an upgrade (verified against the full test suite afterward) or is documented here as an accepted risk with a stated reason, per the plan's "resolve or document any findings."

## How to reproduce

```
cd backend
uv pip install pip-audit --python .venv
.venv/Scripts/python -m pip_audit

cd frontend
npm audit
```

## Frontend

`npm audit`: **0 vulnerabilities.** No action needed.

## Backend: resolved

| Package | Before | After | Why |
|---|---|---|---|
| `python-jose` | 3.3.0 | 3.4.0 | Fixes an algorithm-confusion class of JWT vulnerability (PYSEC-2024-232/233) - directly relevant, this is the library `app/core/security.py` uses to sign/verify every access and refresh token |
| `python-multipart` | 0.0.20 | 0.0.32 | Multiple parsing-related advisories; used for every form/file upload endpoint (login, audio upload) |
| `cryptography` | 44.0.0 | 44.0.1 | Patch release; used for Fernet field-level encryption (`app/core/encryption.py`) |
| `fastapi` | 0.115.6 | 0.115.14 | Latest patch within the 0.115 line (no behavioral changes expected; full test suite re-run and passing) |
| `starlette` | 0.41.3 | 0.46.2 | Explicitly pinned (fastapi 0.115.x otherwise resolves the *minimum* satisfying version, not the latest) to pick up several security fixes within the range fastapi 0.115.x allows (`<0.47.0`) |
| `pyasn1` | 0.4.8 | *(reverted, see below)* | Attempted 0.6.4; blocked by `python-jose`'s own pinned constraint |

All of the above were verified with the full backend test suite (`pytest tests/`, 59/59 passing) after upgrading, both individually and together.

## Backend: accepted risk, documented rather than fixed

| Package | Version | Why not fixed now |
|---|---|---|
| `starlette` | 0.46.2 | Several remaining advisories require starlette >= 0.47 (some >= 1.0), which requires a `fastapi` version whose own dependency ceiling is higher than 0.115.x allows (`fastapi` 0.118+ allows starlette `<0.49.0`; the advisories needing starlette 1.x need an even newer `fastapi`). Jumping fastapi across ~25 minor versions this late is a materially bigger, riskier change than the incremental one already made, and is better done as its own dedicated upgrade with its own dedicated regression pass. Recorded as a follow-up, not silently dropped. |
| `pyasn1` | 0.4.8 | `python-jose[cryptography]==3.4.0` pins `pyasn1>=0.4.1,<0.5.0` in its own metadata; installing 0.6.4 directly makes the dependency set unsatisfiable for a reproducible install (confirmed: `uv pip install -e .` fails to resolve). Manually forcing a newer `pyasn1` outside of `pyproject.toml` was tested and does not break anything at runtime (python-jose's actual use of it is minimal), but is not something `pyproject.toml` can express without either vendoring a patch or migrating off `python-jose` entirely (e.g. to `PyJWT`, which does not depend on `pyasn1` at all). Recorded as a follow-up. |
| `ecdsa` | 0.19.2 | PYSEC-2026-1325 (a known, long-standing timing side-channel in the pure-Python `ecdsa` package; upstream has stated they will not fix it, since constant-time guarantees are out of scope for a pure-Python implementation). **Not reachable in this application**: `JWT_ALGORITHM` defaults to `HS256` (symmetric HMAC) everywhere in this codebase (`app/core/config.py`), and nothing sets it to an ECDSA-family algorithm (`ES256` etc.), so the vulnerable code path is never executed. If this is ever changed to an ECDSA algorithm, re-evaluate. |
| `transformers` | 4.57.6 | The listed advisories are almost entirely about unsafe deserialization when loading an arbitrary/untrusted model (unpickling, `trust_remote_code=True`, etc.). This codebase only ever loads one hardcoded, pinned model id (`sentence-transformers/all-MiniLM-L6-v2`, `app/embeddings/embedder.py`) from the official Hugging Face hub, never accepts a user-supplied model path, and never sets `trust_remote_code=True` anywhere. The attack surface these advisories describe is not reachable through this application's actual usage. A major-version bump (4.x -> 5.x) was not attempted given `sentence-transformers==3.3.1`'s compatibility with `transformers` 5.x was not verified and the risk described is not applicable here. |
| `black`, `pytest` | 24.10.0, 8.3.4 | Dev-only tooling (formatting, test running). Neither ships to, nor executes in, the deployed application - zero production attack surface. Low priority; can be bumped opportunistically in a routine dependency-maintenance pass. |

## A concrete mitigation found and added during this review

While tracing where a provider's raw error response could end up, found that `app/llm/adapters/groq_adapter.py` and `gemini_adapter.py` embedded an *unbounded* provider response body into exception messages, which could reach server logs. Fixed (truncated to 200 characters) - full writeup in `docs/data-flow-review.md`. Not a dependency-audit finding, but found in the course of doing this review, and worth recording alongside it.
