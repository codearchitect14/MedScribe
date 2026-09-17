import { Suspense, lazy } from "react"
import { Routes, Route, Navigate } from "react-router-dom"
import { PublicLayout } from "./components/public/PublicLayout"
import { HomePage } from "./pages/public/HomePage"
import { ProductPage } from "./pages/public/ProductPage"
import { SolutionsPage } from "./pages/public/SolutionsPage"
import { PricingPage } from "./pages/public/PricingPage"
import { AboutPage } from "./pages/public/AboutPage"
import { ContactPage } from "./pages/public/ContactPage"
import { LoginPage } from "./pages/auth/LoginPage"
import { ForgotPasswordPage } from "./pages/auth/ForgotPasswordPage"
import { ProtectedRoute } from "./components/app/ProtectedRoute"
import { AppLayout } from "./components/app/AppLayout"
import { FullPageSpinner } from "./components/ui/Spinner"

// Code-split the authenticated app from the public marketing site: a
// visitor to the public pages (the ones search engines and demo links hit)
// should never download Recharts, TanStack Query's mutation machinery
// beyond what login needs, or the Sentry SDK's app-only usage - none of
// that is needed until someone actually logs in.
const DashboardPage = lazy(() => import("./pages/app/DashboardPage").then((m) => ({ default: m.DashboardPage })))
const NewEncounterPage = lazy(() =>
  import("./pages/app/NewEncounterPage").then((m) => ({ default: m.NewEncounterPage }))
)
const EncounterDetailPage = lazy(() =>
  import("./pages/app/EncounterDetailPage").then((m) => ({ default: m.EncounterDetailPage }))
)
const PatientsPage = lazy(() => import("./pages/app/PatientsPage").then((m) => ({ default: m.PatientsPage })))
const AnalyticsPage = lazy(() => import("./pages/app/AnalyticsPage").then((m) => ({ default: m.AnalyticsPage })))
const SettingsPage = lazy(() => import("./pages/app/SettingsPage").then((m) => ({ default: m.SettingsPage })))

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="product" element={<ProductPage />} />
        <Route path="solutions" element={<SolutionsPage />} />
        <Route path="pricing" element={<PricingPage />} />
        <Route path="about" element={<AboutPage />} />
        <Route path="contact" element={<ContactPage />} />
      </Route>

      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route
            index
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <DashboardPage />
              </Suspense>
            }
          />
          <Route
            path="encounters/new"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <NewEncounterPage />
              </Suspense>
            }
          />
          <Route
            path="encounters/:id"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <EncounterDetailPage />
              </Suspense>
            }
          />
          <Route
            path="patients"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <PatientsPage />
              </Suspense>
            }
          />
          <Route
            path="analytics"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <AnalyticsPage />
              </Suspense>
            }
          />
          <Route
            path="settings"
            element={
              <Suspense fallback={<FullPageSpinner />}>
                <SettingsPage />
              </Suspense>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
