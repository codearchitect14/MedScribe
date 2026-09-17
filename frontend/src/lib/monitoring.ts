// Optional error tracking (plan.md Phase 9: "free tier of Sentry"). A no-op
// unless VITE_SENTRY_DSN is set - no behavior change for a build that
// doesn't configure it. Never sends PII (sendDefaultPii stays false):
// clinical content never leaves the browser except to the backend the user
// is already authenticated against.
import * as Sentry from "@sentry/react"

export function configureMonitoring() {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    sendDefaultPii: false,
    tracesSampleRate: 0,
  })
}
