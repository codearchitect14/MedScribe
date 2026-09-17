import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { Menu, X } from "lucide-react"
import { Logo } from "../Logo"
import { buttonClass } from "../ui/Button"

const links = [
  { to: "/product", label: "Product" },
  { to: "/solutions", label: "Solutions" },
  { to: "/pricing", label: "Pricing" },
  { to: "/about", label: "About" },
  { to: "/contact", label: "Contact" },
]

export function PublicNavbar() {
  const [open, setOpen] = useState(false)

  return (
    <header className="sticky top-0 z-40 border-b border-ink-100 bg-white/90 backdrop-blur">
      <div className="section flex h-16 items-center justify-between">
        <Logo />

        <nav className="hidden items-center gap-8 md:flex">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `text-sm font-medium transition-colors ${
                  isActive ? "text-brand-700" : "text-ink-600 hover:text-ink-900"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link to="/login" className="text-sm font-semibold text-ink-700 hover:text-ink-900">
            Log in
          </Link>
          <Link to="/contact" className={buttonClass("primary", "sm")}>
            Request a demo
          </Link>
        </div>

        <button
          className="rounded-lg p-2 text-ink-700 hover:bg-ink-100 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-ink-100 bg-white px-6 py-4 md:hidden">
          <nav className="flex flex-col gap-3">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setOpen(false)}
                className="text-sm font-medium text-ink-700"
              >
                {link.label}
              </NavLink>
            ))}
            <Link to="/login" onClick={() => setOpen(false)} className="text-sm font-semibold text-ink-900">
              Log in
            </Link>
            <Link
              to="/contact"
              onClick={() => setOpen(false)}
              className="rounded-lg bg-brand-600 px-4 py-2 text-center text-sm font-semibold text-white"
            >
              Request a demo
            </Link>
          </nav>
        </div>
      )}
    </header>
  )
}
