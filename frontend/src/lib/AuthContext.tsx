import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react"
import type { User } from "../types/api"
import { setTokens } from "./authStore"
import { fetchMe, login as loginRequest, logout as logoutRequest } from "./endpoints"
import { refreshSession } from "./api"

interface AuthContextValue {
  user: User | null
  status: "loading" | "authenticated" | "unauthenticated"
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading")

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // On page load there is no access token in memory, but the refresh
      // token cookie may still be valid: attempt a silent refresh so a
      // reload does not force a fresh login.
      const refreshed = await refreshSession()
      if (!refreshed) {
        if (!cancelled) setStatus("unauthenticated")
        return
      }
      try {
        const me = await fetchMe()
        if (!cancelled) {
          setUser(me)
          setStatus("authenticated")
        }
      } catch {
        if (!cancelled) setStatus("unauthenticated")
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await loginRequest(email, password)
    setTokens({ accessToken: tokens.access_token, csrfToken: tokens.csrf_token })
    const me = await fetchMe()
    setUser(me)
    setStatus("authenticated")
  }, [])

  const logout = useCallback(async () => {
    await logoutRequest()
    setTokens({ accessToken: null, csrfToken: null })
    setUser(null)
    setStatus("unauthenticated")
  }, [])

  return <AuthContext.Provider value={{ user, status, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
