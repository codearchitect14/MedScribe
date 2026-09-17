import type { ReactNode } from "react"
import clsx from "clsx"

export function StatTile({
  label,
  value,
  hint,
  icon,
  tone = "brand",
}: {
  label: string
  value: string
  hint?: string
  icon?: ReactNode
  tone?: "brand" | "teal" | "amber" | "rose"
}) {
  const toneBg: Record<string, string> = {
    brand: "bg-brand-50 text-brand-600",
    teal: "bg-teal-50 text-accent-teal",
    amber: "bg-amber-50 text-accent-amber",
    rose: "bg-rose-50 text-accent-rose",
  }
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-ink-500">{label}</p>
        {icon && <div className={clsx("rounded-lg p-2", toneBg[tone])}>{icon}</div>}
      </div>
      <p className="mt-2 text-2xl font-bold tracking-tight text-ink-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
    </div>
  )
}
