import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuth } from "../../lib/AuthContext"
import { FullPageSpinner } from "../ui/Spinner"

export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === "loading") {
    return <FullPageSpinner />
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
