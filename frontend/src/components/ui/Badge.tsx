import type { HTMLAttributes } from "react"
import clsx from "clsx"

type Tone = "neutral" | "brand" | "success" | "warning" | "danger"

const toneClasses: Record<Tone, string> = {
  neutral: "bg-ink-100 text-ink-700",
  brand: "bg-brand-100 text-brand-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-800",
  danger: "bg-rose-100 text-rose-700",
}

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
}

export function Badge({ tone = "neutral", className, ...rest }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        toneClasses[tone],
        className
      )}
      {...rest}
    />
  )
}

const STATUS_TONE: Record<string, Tone> = {
  recording: "danger",
  transcribed: "neutral",
  note_generated: "brand",
  under_review: "warning",
  finalized: "success",
  coded: "success",
  billed: "success",
}

export function EncounterStatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? "neutral"} className="capitalize">
      {status.replace(/_/g, " ")}
    </Badge>
  )
}
