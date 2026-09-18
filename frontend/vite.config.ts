import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'

// Proxies known backend route prefixes through the Vite dev server's own
// origin, so the browser treats API calls as same-site rather than
// cross-origin. This matters specifically for the refresh-token cookie
// (SameSite=Strict, see backend/app/core/cookies.py): a cookie set by
// 127.0.0.1:8102 is never sent on a fetch from localhost:5173 (different
// origin), which breaks the silent-refresh-on-reload flow. Proxying mirrors
// how this would be deployed for real too - frontend and backend behind one
// origin via a reverse proxy - rather than special-casing dev.
// Every prefix here must be a path no public frontend page also owns: this
// list is matched against the raw request path before React Router ever
// sees it, so a collision (e.g. an API resource at the same path as a
// marketing page) silently serves the API's JSON instead of the page on a
// direct visit or hard refresh. That's why the contact API lives at
// /contact-requests rather than /contact - the public site's own /contact
// page would otherwise never render server-side.
const BACKEND_ROUTE_PREFIXES = [
  '/auth',
  '/users',
  '/organizations',
  '/patients',
  '/encounters',
  '/ws',
  '/tasks',
  '/reimbursement-rates',
  '/analytics',
  '/contact-requests',
  '/health',
]

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendTarget = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

  const proxy: Record<string, ProxyOptions> = {}
  for (const prefix of BACKEND_ROUTE_PREFIXES) {
    proxy[prefix] = { target: backendTarget, changeOrigin: true, ws: true }
  }

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy,
    },
  }
})
