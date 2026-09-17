import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router-dom"
import { QueryClientProvider } from "@tanstack/react-query"
import App from "./App.tsx"
import { AuthProvider } from "./lib/AuthContext.tsx"
import { queryClient } from "./lib/queryClient.ts"
import { configureMonitoring } from "./lib/monitoring.ts"
import "./index.css"

configureMonitoring()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
)
