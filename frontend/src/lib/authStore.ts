// A tiny module-level store for the access token and CSRF token, outside
// React state, so the plain fetch wrapper in api.ts can read the current
// token without needing a hook. The access token is held only in memory
// (never localStorage) per docs/security.md: the refresh token lives in an
// httpOnly cookie the browser manages, and this module never sees it.
let accessToken: string | null = null
let csrfToken: string | null = null

export function setTokens(tokens: { accessToken: string | null; csrfToken: string | null }) {
  accessToken = tokens.accessToken
  csrfToken = tokens.csrfToken
}

export function getAccessToken() {
  return accessToken
}

export function getCsrfToken() {
  return csrfToken
}

export function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}
