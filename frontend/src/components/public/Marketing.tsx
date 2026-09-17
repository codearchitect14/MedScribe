import type { ReactNode } from "react"
import clsx from "clsx"

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="mb-3 inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand-700">
      {children}
    </p>
  )
}

export function SectionHeading({
  eyebrow,
  title,
  subtitle,
  align = "center",
}: {
  eyebrow?: string
  title: string
  subtitle?: string
  align?: "center" | "left"
}) {
  return (
    <div className={clsx("mx-auto max-w-3xl", align === "center" ? "text-center" : "text-left ml-0")}>
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="text-balance text-3xl font-bold tracking-tight text-ink-900 sm:text-4xl">{title}</h2>
      {subtitle && <p className="mt-4 text-lg text-ink-500">{subtitle}</p>}
    </div>
  )
}

export function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: ReactNode
  title: string
  description: string
}) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
        {icon}
      </div>
      <h3 className="mt-4 text-lg font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink-500">{description}</p>
    </div>
  )
}

export function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <p className="text-4xl font-bold tracking-tight text-white">{value}</p>
      <p className="mt-1 text-sm text-brand-100">{label}</p>
    </div>
  )
}

export function TestimonialCard({ quote, name, role }: { quote: string; name: string; role: string }) {
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-7 shadow-sm">
      <p className="text-ink-700">&ldquo;{quote}&rdquo;</p>
      <div className="mt-5 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
          {name
            .split(" ")
            .map((n) => n[0])
            .join("")}
        </div>
        <div>
          <p className="text-sm font-semibold text-ink-900">{name}</p>
          <p className="text-xs text-ink-500">{role}</p>
        </div>
      </div>
    </div>
  )
}

export function StepCard({ step, title, description }: { step: number; title: string; description: string }) {
  return (
    <div className="relative rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-full bg-ink-900 text-sm font-bold text-white">
        {step}
      </div>
      <h3 className="mt-4 text-base font-semibold text-ink-900">{title}</h3>
      <p className="mt-2 text-sm text-ink-500">{description}</p>
    </div>
  )
}

export function CtaBanner({
  title,
  subtitle,
  primaryHref,
  primaryLabel,
}: {
  title: string
  subtitle: string
  primaryHref: string
  primaryLabel: string
}) {
  return (
    <section className="section py-16">
      <div className="overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 to-brand-900 px-8 py-14 text-center sm:px-16">
        <h2 className="text-balance text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>
        <p className="mx-auto mt-4 max-w-xl text-brand-100">{subtitle}</p>
        <a
          href={primaryHref}
          className="mt-8 inline-flex items-center justify-center rounded-lg bg-white px-6 py-3 text-sm font-semibold text-brand-800 shadow-sm transition-colors hover:bg-brand-50"
        >
          {primaryLabel}
        </a>
      </div>
    </section>
  )
}
