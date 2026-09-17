import type { ReactNode } from "react"
import clsx from "clsx"
import { AlertTriangle, CheckCircle2, Info } from "lucide-react"

type Tone = "info" | "success" | "error"

const toneStyles: Record<Tone, { wrap: string; icon: ReactNode }> = {
  info: { wrap: "bg-brand-50 text-brand-800 border-brand-100", icon: <Info className="h-4 w-4" /> },
  success: {
    wrap: "bg-emerald-50 text-emerald-800 border-emerald-100",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  error: { wrap: "bg-rose-50 text-rose-800 border-rose-100", icon: <AlertTriangle className="h-4 w-4" /> },
}

export function Alert({ tone = "info", children }: { tone?: Tone; children: ReactNode }) {
  const styles = toneStyles[tone]
  return (
    <div className={clsx("flex items-start gap-2 rounded-lg border px-3.5 py-2.5 text-sm", styles.wrap)}>
      <span className="mt-0.5">{styles.icon}</span>
      <div>{children}</div>
    </div>
  )
}
