# Frontend (Phase 8)

React (Vite) + TypeScript + Tailwind CSS v4, in `frontend/`: a public marketing site and the full authenticated application from Phases 4, 5, and 7, in one codebase with a clear split between public and authenticated routes.

## Stack

- **Vite + React 19 + TypeScript**, React Router for routing, TanStack Query for server state (caching, mutations, invalidation).
- **Tailwind CSS v4** (`@tailwindcss/vite`, no separate config file - design tokens live in `src/index.css`'s `@theme` block: a `brand` and `ink` color scale, plus `accent-teal`/`accent-amber`/`accent-rose`). The same tokens and the same shared UI components (`src/components/ui/`) are used on both the public site and the authenticated app, so the transition between them is visually consistent, per the plan's design-system requirement.
- **Recharts** for the analytics dashboard, **lucide-react** for icons.

## Structure

```
src/
  components/
    ui/          Button, Card, Badge, Input/Textarea/Select, Tabs, Alert, Spinner, StatTile - the design system primitives
    public/       Navbar, footer, layout, and marketing-page building blocks (SectionHeading, FeatureCard, etc.)
    app/          AppLayout (sidebar shell), ProtectedRoute (auth guard)
  pages/
    public/       Home, Product, Solutions, Pricing, About, Contact
    auth/         Login, ForgotPassword
    app/          Dashboard, NewEncounter, EncounterDetail, Patients, Analytics, Settings
  lib/
    api.ts         fetch wrapper: attaches the bearer token, retries once on 401 via a silent refresh
    authStore.ts    in-memory access/CSRF token holder (never localStorage - see Auth below)
    AuthContext.tsx  React context wrapping login/logout/current-user state
    endpoints.ts     one typed function per backend endpoint the UI calls
    useLiveRecorder.ts  the live-transcription WebSocket + microphone capture hook
  types/api.ts    TypeScript interfaces mirroring the backend's Pydantic schemas
public/
  pcm-worklet.js  AudioWorkletProcessor: converts mic audio to 16-bit PCM for the live transcription WebSocket
```

## Auth model (matches docs/security.md)

The access token lives only in a module-level JS variable (`authStore.ts`), never in `localStorage` or a cookie the frontend controls - a page reload wipes it, by design. `AuthProvider` handles that on mount by attempting a silent refresh (`POST /auth/refresh`) using the refresh-token cookie, which the backend manages as `httpOnly`. If that succeeds, `GET /auth/me` restores the session transparently; if not, the user lands on `/login`.

**Why the Vite dev server proxies the API (`vite.config.ts`).** The refresh cookie is `SameSite=Strict`. A cookie set by a backend on one origin is never sent on a `fetch` from a different origin, even for `credentials: "include"` - so with the frontend on `localhost:5173` and the backend on a different host/port, the silent-refresh-on-reload flow would silently fail after every full page reload. `vite.config.ts` proxies every backend route prefix (`/auth`, `/encounters`, `/ws`, etc.) through the frontend's own dev-server origin, so the browser only ever talks to one origin and the cookie is same-site. This is also the right shape for a real deployment: front the built frontend and the backend with one reverse-proxy origin, not two CORS-negotiated ones. Set `VITE_BACKEND_URL` to point the proxy at your running backend (see `.env.example`); `VITE_API_BASE_URL` is only for the rare case of a production build served from an origin with no proxy in front of it.

## Live transcription

`useLiveRecorder` drives the Phase 5 WebSocket protocol end to end: `POST /encounters/live` to get an encounter id, connect to `/ws/encounters/{id}/live-transcribe?token=...`, wait for `ready` (handling `queued` if the worker pool is full), then capture the microphone via `AudioContext({ sampleRate: 16000 })` + an `AudioWorkletNode` (`public/pcm-worklet.js`) that converts Float32 audio to the raw PCM16 format the backend expects, streaming it over the socket. Partial/final transcript segments update the UI live; `stop` finalizes the encounter and hands off directly into the SOAP note flow, exactly as `docs/live-transcription.md` specifies.

## What's verified vs. what isn't

Verified against a real running backend and a real browser (Playwright, headless Chromium) in this environment: every public page renders with no console errors; login persists across full page reloads (the cookie/proxy fix above); patient creation, encounter creation from a pasted transcript, and navigation through all encounter tabs work end to end against live API responses; the analytics, patients, and settings screens render correctly with real (empty-state) data; desktop, tablet (834px), and mobile (390px) layouts all render correctly, including the collapsing sidebar.

**Not verified in this environment**, consistent with every backend phase that touches the same dependency: actually generating a SOAP note/care plan/codes requires a real Groq or Gemini API key, which is not configured here. The UI's error handling for that case *is* verified - a failed generation surfaces a clear inline error rather than crashing (see the encounter-detail screenshot in this phase's work). Live microphone capture is implemented against the real Web Audio API but was not exercised with a live microphone in this headless environment.

**Not built in this pass:** a frontend automated test suite (Vitest + React Testing Library, named in the Phase 0 tech stack) and an actual production deployment (Phase 9). Patient search/filtering on the Patients list is intentionally absent - patient names are encrypted at rest on the backend (`docs/hardening.md`), so there is nothing to search against at the SQL level without a separate searchable index.
