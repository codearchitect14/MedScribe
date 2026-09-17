import { useState } from "react"
import { NavLink, Outlet, useNavigate } from "react-router-dom"
import {
  LayoutDashboard,
  Mic,
  Users,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react"
import clsx from "clsx"
import { Logo } from "../Logo"
import { useAuth } from "../../lib/AuthContext"

const navItems = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/encounters/new", label: "New Encounter", icon: Mic },
  { to: "/app/patients", label: "Patients", icon: Users },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3, roles: ["admin", "super_admin"] },
  { to: "/app/settings", label: "Settings", icon: Settings, roles: ["admin", "super_admin"] },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)

  async function handleLogout() {
    await logout()
    navigate("/login", { replace: true })
  }

  const visibleItems = navItems.filter((item) => !item.roles || (user && item.roles.includes(user.role)))

  const sidebarContent = (
    <>
      <div className="px-5 py-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-50 hover:text-ink-900"
              )
            }
          >
            <item.icon className="h-[18px] w-[18px]" />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-ink-100 px-3 py-4">
        <div className="flex items-center gap-3 rounded-lg px-3 py-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
            {user?.full_name?.[0]?.toUpperCase() ?? "U"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-ink-900">{user?.full_name}</p>
            <p className="truncate text-xs capitalize text-ink-400">{user?.role.replace("_", " ")}</p>
          </div>
          <button
            onClick={handleLogout}
            className="rounded-lg p-2 text-ink-400 hover:bg-ink-100 hover:text-ink-700"
            aria-label="Log out"
            title="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </>
  )

  return (
    <div className="flex min-h-screen bg-ink-50/40">
      <aside className="hidden w-64 flex-col border-r border-ink-100 bg-white lg:flex">{sidebarContent}</aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div className="absolute inset-0 bg-ink-900/40" onClick={() => setMobileOpen(false)} />
          <aside className="relative flex w-64 flex-col bg-white shadow-xl">{sidebarContent}</aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center border-b border-ink-100 bg-white px-4 lg:hidden">
          <button onClick={() => setMobileOpen(true)} className="rounded-lg p-2 text-ink-700 hover:bg-ink-100">
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="ml-3">
            <Logo />
          </div>
        </header>
        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
