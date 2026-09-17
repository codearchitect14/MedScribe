import { Stethoscope, Building2, Hospital } from "lucide-react"
import { Eyebrow, CtaBanner } from "../../components/public/Marketing"

const audiences = [
  {
    icon: <Stethoscope className="h-6 w-6" />,
    title: "Independent clinicians",
    description:
      "Solo and small-practice clinicians who lose hours a week to charting after clinic hours.",
    points: [
      "Live recording built into the visit, no separate dictation app",
      "Finish notes before the next patient, not after dinner",
      "No per-minute transcription costs to budget around",
    ],
  },
  {
    icon: <Building2 className="h-6 w-6" />,
    title: "Multi-provider clinics",
    description: "Practices coordinating documentation, coding, and billing across several clinicians.",
    points: [
      "Role-based access for clinicians, coders, and administrators",
      "A shared coding review queue so coders work across the whole practice, not one chart at a time",
      "Practice-wide analytics: volume, coding mix, and turnaround time in one dashboard",
    ],
  },
  {
    icon: <Hospital className="h-6 w-6" />,
    title: "Health systems",
    description: "Organizations that need documentation productivity data alongside compliance controls.",
    points: [
      "Organization-level data isolation enforced at the query layer, not just the UI",
      "Full audit logging of authentication and record access events",
      "A reference architecture your engineering team can extend or self-host",
    ],
  },
]

export function SolutionsPage() {
  return (
    <>
      <section className="section py-16 text-center sm:py-24">
        <Eyebrow>Solutions</Eyebrow>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          Built for how your team actually works
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-500">
          The same platform, tailored to the scale you operate at - from a single clinician to a multi-site
          health system.
        </p>
      </section>

      <section className="section grid gap-8 pb-20 lg:grid-cols-3">
        {audiences.map((a) => (
          <div key={a.title} className="rounded-2xl border border-ink-100 bg-white p-7 shadow-sm">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
              {a.icon}
            </div>
            <h2 className="mt-5 text-xl font-bold text-ink-900">{a.title}</h2>
            <p className="mt-2 text-sm text-ink-500">{a.description}</p>
            <ul className="mt-5 space-y-2">
              {a.points.map((point) => (
                <li key={point} className="flex items-start gap-2 text-sm text-ink-600">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                  {point}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <CtaBanner
        title="Not sure which fits your team?"
        subtitle="Tell us how your practice is structured and we will recommend a rollout plan."
        primaryHref="/contact"
        primaryLabel="Talk to us"
      />
    </>
  )
}
