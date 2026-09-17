// Empty by default: requests go to a relative path on the frontend's own
// origin, proxied to the backend by Vite in dev (see vite.config.ts) or by
// a reverse proxy in production. This keeps auth cookies same-site; see the
// comment in vite.config.ts for why that matters. Set VITE_API_BASE_URL
// only if the backend is genuinely served from a different origin than the
// frontend with no proxy in front of it.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ""
