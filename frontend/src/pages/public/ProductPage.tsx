import { Mic, FileText, ClipboardList, Tags } from "lucide-react"
import { SectionHeading, Eyebrow } from "../../components/public/Marketing"
import { CtaBanner } from "../../components/public/Marketing"

const walkthroughs = [
  {
    icon: <Mic className="h-6 w-6" />,
    title: "Capture the encounter",
    description:
      "Record live in the browser with real-time partial transcription, upload a completed audio file, or paste an existing transcript. All three paths land in the same review workflow.",
    points: [
      "Self-hosted speech recognition - no per-minute transcription billing",
      "Speaker labels and filler words cleaned automatically before generation",
      "Live sessions checkpoint every few seconds so nothing is lost on a dropped connection",
    ],
  },
  {
    icon: <FileText className="h-6 w-6" />,
    title: "Generate the SOAP note",
    description:
      "One structured prompt returns all four SOAP sections at once. The note is always a draft until a clinician reviews and finalizes it.",
    points: [
      "Edit any section before finalizing",
      "Explicit draft -> under review -> finalized workflow, enforced by the system",
      "Every generated note is timestamped and attributable to the model that produced it",
    ],
  },
  {
    icon: <ClipboardList className="h-6 w-6" />,
    title: "Produce the care plan",
    description:
      "Built from the finalized Assessment and Plan only - never the raw transcript again - keeping generation fast and focused.",
    points: [
      "Follow-up actions, medications, and patient education in one structured document",
      "Medication suggestions always flagged as requiring clinician confirmation",
    ],
  },
  {
    icon: <Tags className="h-6 w-6" />,
    title: "Confirm the codes",
    description:
      "Candidate ICD-10 and HCPCS codes are retrieved from a real, versioned reference database by semantic similarity to the assessment, then ranked and justified - never invented from model memory.",
    points: [
      "Coders can accept or reject each suggestion individually",
      "Confidence score shown per code",
      "Accepted codes flow directly into billing and revenue analytics",
    ],
  },
]

export function ProductPage() {
  return (
    <>
      <section className="section py-16 text-center sm:py-24">
        <Eyebrow>Product</Eyebrow>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          One workflow, from conversation to coded record
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-500">
          A closer look at how MedScribe AI turns an encounter into a finalized, billable record - and where a
          clinician stays in control at every step.
        </p>
      </section>

      <section className="section space-y-16 pb-20">
        {walkthroughs.map((w, i) => (
          <div
            key={w.title}
            className={`grid items-center gap-10 lg:grid-cols-2 ${i % 2 === 1 ? "lg:[&>*:first-child]:order-2" : ""}`}
          >
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                {w.icon}
              </div>
              <h2 className="mt-5 text-2xl font-bold text-ink-900">{w.title}</h2>
              <p className="mt-3 text-ink-500">{w.description}</p>
              <ul className="mt-5 space-y-2">
                {w.points.map((point) => (
                  <li key={point} className="flex items-start gap-2 text-sm text-ink-600">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-2xl border border-ink-100 bg-ink-50/60 p-10">
              <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-ink-200 text-sm text-ink-400">
                {w.title} screenshot
              </div>
            </div>
          </div>
        ))}
      </section>

      <div className="bg-ink-50/60 py-20">
        <div className="section">
          <SectionHeading eyebrow="Under the hood" title="Provider-agnostic by design" />
          <p className="mx-auto mt-6 max-w-2xl text-center text-ink-500">
            Every generation call goes through one internal gateway that can fail over between two free-tier LLM
            providers automatically, with strict JSON schema validation and per-call usage logging - so a rate
            limit on one provider never stops a clinician mid-note.
          </p>
        </div>
      </div>

      <CtaBanner
        title="See the full workflow on your own transcripts"
        subtitle="We will walk through a live encounter, end to end, with your team."
        primaryHref="/contact"
        primaryLabel="Request a demo"
      />
    </>
  )
}
