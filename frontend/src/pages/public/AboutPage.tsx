import { Eyebrow, SectionHeading, CtaBanner } from "../../components/public/Marketing"

const values = [
  {
    title: "Clinicians stay in control",
    description:
      "Every AI-generated document is a draft until a clinician reviews and finalizes it. This is a documentation productivity tool, not a diagnostic tool.",
  },
  {
    title: "Real data over model memory",
    description:
      "Medical codes are always retrieved from a versioned reference database and only ranked by the model - never invented from memory.",
  },
  {
    title: "Security by default",
    description:
      "Role-based access control, encrypted patient identifiers, and audit logging are part of the foundation, not an add-on.",
  },
  {
    title: "Built in the open",
    description:
      "The entire platform is built from freely available, open-source, and free-tier technology, so it can be studied, self-hosted, and extended.",
  },
]

export function AboutPage() {
  return (
    <>
      <section className="section py-16 text-center sm:py-24">
        <Eyebrow>About</Eyebrow>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          Documentation shouldn&apos;t cost clinicians their evenings
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-500">
          MedScribe AI exists to give the time spent on notes, coding lookups, and billing paperwork back to
          patient care.
        </p>
      </section>

      <section className="section grid gap-10 pb-20 lg:grid-cols-2 lg:items-center">
        <div>
          <h2 className="text-2xl font-bold text-ink-900">Our story</h2>
          <p className="mt-4 text-ink-500">
            Ambient scribing products have shown that clinicians can get hours back every week when
            documentation is handled well. MedScribe AI was built as an open, self-buildable reference for that
            idea: a full pipeline from a raw conversation to a finalized, coded clinical record, built entirely
            on free and open-source infrastructure so any team can study it, run it, or extend it.
          </p>
          <p className="mt-4 text-ink-500">
            Every part of the system - transcription, note generation, coding, and analytics - is designed
            around one rule: the model structures and suggests, the clinician decides.
          </p>
        </div>
        <div className="rounded-2xl border border-ink-100 bg-ink-50/60 p-10">
          <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-ink-200 text-sm text-ink-400">
            Team photo
          </div>
        </div>
      </section>

      <section className="bg-ink-50/60 py-20">
        <div className="section">
          <SectionHeading eyebrow="What we believe" title="Principles that shape every feature" />
          <div className="mt-12 grid gap-6 sm:grid-cols-2">
            {values.map((v) => (
              <div key={v.title} className="rounded-2xl border border-ink-100 bg-white p-6 shadow-sm">
                <h3 className="text-base font-semibold text-ink-900">{v.title}</h3>
                <p className="mt-2 text-sm text-ink-500">{v.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <CtaBanner
        title="Want to see how it's built?"
        subtitle="We are happy to walk through the architecture with your engineering or compliance team."
        primaryHref="/contact"
        primaryLabel="Get in touch"
      />
    </>
  )
}
