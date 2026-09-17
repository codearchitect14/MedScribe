import { Link } from "react-router-dom"
import { Logo } from "../Logo"

const columns = [
  {
    title: "Product",
    links: [
      { label: "Overview", to: "/product" },
      { label: "Solutions", to: "/solutions" },
      { label: "Pricing", to: "/pricing" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", to: "/about" },
      { label: "Contact", to: "/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Privacy", to: "/contact" },
      { label: "Security", to: "/contact" },
    ],
  },
]

export function PublicFooter() {
  return (
    <footer className="border-t border-ink-100 bg-ink-50/60">
      <div className="section grid grid-cols-2 gap-10 py-14 md:grid-cols-5">
        <div className="col-span-2">
          <Logo />
          <p className="mt-4 max-w-xs text-sm text-ink-500">
            Ambient clinical documentation and AI-assisted coding, built with HIPAA-aligned security practices.
          </p>
        </div>
        {columns.map((col) => (
          <div key={col.title}>
            <p className="text-sm font-semibold text-ink-900">{col.title}</p>
            <ul className="mt-3 space-y-2">
              {col.links.map((link) => (
                <li key={link.label}>
                  <Link to={link.to} className="text-sm text-ink-500 hover:text-ink-800">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-ink-100 py-6">
        <div className="section flex flex-col items-center justify-between gap-2 text-xs text-ink-400 sm:flex-row">
          <p>&copy; {new Date().getFullYear()} MedScribe AI. All rights reserved.</p>
          <p>Documentation productivity software. Not a diagnostic tool. Clinician review required.</p>
        </div>
      </div>
    </footer>
  )
}
