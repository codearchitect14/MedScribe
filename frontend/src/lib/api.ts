import { API_BASE_URL } from "./config"
import { getAccessToken, getCsrfToken, readCsrfCookie, setTokens } from "./authStore"
import type { AccessTokenResponse } from "../types/api"

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Request failed with status ${status}`)
    this.status = status
    this.detail = detail
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown
  isForm?: boolean
  skipAuthRetry?: boolean
}

async function parseErrorDetail(response: Response): Promise<unknown> {
  try {
    const data = await response.json()
    return data?.detail ?? data
  } catch {
    return response.statusText
  }
}

let refreshInFlight: Promise<boolean> | null = null

export async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const csrf = getCsrfToken() ?? readCsrfCookie()
    if (!csrf) return false
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrf },
      })
      if (!response.ok) {
        setTokens({ accessToken: null, csrfToken: null })
        return false
      }
      const data: AccessTokenResponse = await response.json()
      setTokens({ accessToken: data.access_token, csrfToken: data.csrf_token })
      return true
    } catch {
      return false
    }
  })()
  const result = await refreshInFlight
  refreshInFlight = null
  return result
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, isForm, skipAuthRetry, headers, ...rest } = options
  const token = getAccessToken()

  const finalHeaders: Record<string, string> = {
    ...(isForm ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(headers as Record<string, string> | undefined),
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    credentials: "include",
    headers: finalHeaders,
    body: body === undefined ? undefined : isForm ? (body as BodyInit) : JSON.stringify(body),
  })

  if (response.status === 401 && !skipAuthRetry && path !== "/auth/login") {
    const refreshed = await refreshSession()
    if (refreshed) {
      return apiRequest<T>(path, { ...options, skipAuthRetry: true })
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response))
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get("content-type") ?? ""
  if (contentType.includes("application/json")) {
    return (await response.json()) as T
  }
  return (await response.blob()) as unknown as T
}

export function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ""
}
