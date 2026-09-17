import { Link } from "react-router-dom"
import clsx from "clsx"

export function Logo({ className, dark }: { className?: string; dark?: boolean }) {
  return (
    <Link to="/" className={clsx("flex items-center gap-2", className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white">
        <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
          <path
            d="M9 21V11l7 6 7-6v10"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
        </svg>
      </span>
      <span className={clsx("text-lg font-bold tracking-tight", dark ? "text-white" : "text-ink-900")}>
        MedScribe<span className="text-brand-600">AI</span>
      </span>
    </Link>
  )
}
