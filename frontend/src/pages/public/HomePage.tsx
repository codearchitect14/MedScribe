import { Link } from "react-router-dom"
import {
  Mic,
  FileText,
  ClipboardList,
  Tags,
  BarChart3,
  ShieldCheck,
  PlayCircle,
} from "lucide-react"
import { buttonClass } from "../../components/ui/Button"
import {
  SectionHeading,
  FeatureCard,
  StatBlock,
  TestimonialCard,
  StepCard,
  CtaBanner,
  Eyebrow,
} from "../../components/public/Marketing"

const features = [
  {
    icon: <Mic className="h-5 w-5" />,
    title: "Ambient transcription",
    description:
      "Capture the encounter live in the browser, from an uploaded recording, or pasted text - all transcribed with self-hosted speech recognition.",
  },
  {
    icon: <FileText className="h-5 w-5" />,
    title: "Automated SOAP notes",
    description:
      "A structured Subjective, Objective, Assessment, and Plan note generated in seconds, editable and reviewable before it becomes official.",
  },
  {
    icon: <ClipboardList className="h-5 w-5" />,
    title: "Automated care plans",
    description:
      "Follow-up actions, medications, and patient education generated directly from the finalized assessment and plan.",
  },
  {
    icon: <Tags className="h-5 w-5" />,
    title: "AI-assisted medical coding",
    description:
      "ICD-10 and HCPCS suggestions retrieved from a real, versioned code database and ranked by relevance - never invented from memory.",
  },
  {
    icon: <BarChart3 className="h-5 w-5" />,
    title: "Analytics and revenue insights",
    description:
      "Encounter volume, coding mix, turnaround time, and estimated reimbursement, pre-aggregated for a fast, explainable dashboard.",
  },
  {
    icon: <ShieldCheck className="h-5 w-5" />,
    title: "Enterprise-grade security",
    description:
      "Role-based access control, encrypted patient identifiers, audit logging, and a CSRF-protected session model, built with HIPAA-aligned security practices.",
  },
]

const steps = [
  { title: "Record or paste the encounter", description: "Start a live recording, upload audio, or paste an existing transcript." },
  { title: "Review the generated note", description: "Edit any section of the AI-drafted SOAP note, then move it into review." },
  { title: "Confirm codes", description: "Accept or reject ICD-10/HCPCS suggestions retrieved from the reference code database." },
  { title: "Sync to your workflow", description: "Finalize, bill, and track revenue and productivity from one dashboard." },
]

const specialties = [
  "Family Medicine",
  "Internal Medicine",
  "Pediatrics",
  "Behavioral Health",
  "Orthopedics",
  "Dermatology",
  "Cardiology",
  "Urgent Care",
]

export function HomePage() {
  return (
    <>
      <section className="section grid gap-12 py-16 sm:py-24 lg:grid-cols-2 lg:items-center">
        <div>
          <Eyebrow>Ambient clinical documentation</Eyebrow>
          <h1 className="text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
            Give clinicians back their time, not their charting.
          </h1>
          <p className="mt-6 text-lg text-ink-500">
            MedScribe AI turns doctor-patient conversations into structured SOAP notes, care plans, and
            billing-ready codes in seconds - so your clinicians spend their day with patients, not paperwork.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link to="/contact" className={buttonClass("primary", "lg")}>
              Request a demo
            </Link>
            <Link to="/product" className="inline-flex items-center gap-2 text-sm font-semibold text-ink-700 hover:text-ink-900">
              <PlayCircle className="h-5 w-5" />
              Watch demo
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap items-center gap-x-8 gap-y-3 text-xs font-medium uppercase tracking-wide text-ink-400">
            <span>Built with HIPAA-aligned security practices</span>
            <span>Free and open-source LLM infrastructure</span>
          </div>
        </div>

        <div className="rounded-2xl border border-ink-100 bg-white p-3 shadow-xl">
          <div className="rounded-xl bg-ink-900 p-4">
            <div className="flex items-center gap-1.5 pb-3">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            </div>
            <div className="space-y-3 rounded-lg bg-ink-800 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-brand-300">Assessment</p>
              <p className="text-sm text-ink-100">
                Type 2 diabetes mellitus with hyperglycemia, suboptimal control on current metformin dose.
              </p>
              <p className="text-xs font-semibold uppercase tracking-wide text-brand-300">Plan</p>
              <p className="text-sm text-ink-100">Increase metformin dose. Recheck A1C in three months.</p>
              <div className="flex flex-wrap gap-2 pt-1">
                <span className="rounded-full bg-emerald-500/20 px-2.5 py-1 text-xs font-medium text-emerald-300">
                  E11.65 &middot; 92% confidence
                </span>
                <span className="rounded-full bg-brand-500/20 px-2.5 py-1 text-xs font-medium text-brand-300">
                  99214 &middot; suggested
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y border-ink-100 bg-ink-50/60 py-8">
        <div className="section flex flex-wrap items-center justify-center gap-x-12 gap-y-4 text-sm font-semibold text-ink-400">
          <span>HIPAA-ALIGNED SECURITY PRACTICES</span>
          <span>SOC 2-STYLE READINESS</span>
          <span>ENCRYPTED AT REST</span>
          <span>ROLE-BASED ACCESS CONTROL</span>
          <span>AUDIT LOGGED</span>
        </div>
      </section>

      <section className="section py-20">
        <SectionHeading
          eyebrow="Platform"
          title="Everything a documentation-heavy practice needs"
          subtitle="From the first word of the encounter to a coded, billable record."
        />
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </section>

      <section className="bg-ink-50/60 py-20">
        <div className="section">
          <SectionHeading eyebrow="How it works" title="From conversation to coded record in four steps" />
          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((s, i) => (
              <StepCard key={s.title} step={i + 1} {...s} />
            ))}
          </div>
        </div>
      </section>

      <section className="section py-20">
        <SectionHeading eyebrow="Built for" title="Every clinical specialty" />
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {specialties.map((s) => (
            <span
              key={s}
              className="rounded-full border border-ink-200 bg-white px-4 py-2 text-sm font-medium text-ink-600"
            >
              {s}
            </span>
          ))}
        </div>
      </section>

      <section className="bg-ink-900 py-20">
        <div className="section grid gap-10 sm:grid-cols-3">
          <StatBlock value="70%" label="Reduction in documentation time (target)" />
          <StatBlock value="&lt; 30s" label="Average time to a drafted SOAP note" />
          <StatBlock value="99%+" label="Codes retrieved from real reference data, never invented" />
        </div>
      </section>

      <section className="section py-20">
        <SectionHeading eyebrow="What clinicians say" title="Trusted by care teams who hate typing" />
        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          <TestimonialCard
            quote="I finish my notes before the patient leaves the room. That never happened before."
            name="A. Reyes, MD"
            role="Family Medicine Physician"
          />
          <TestimonialCard
            quote="The coding suggestions actually match our documentation, not just a keyword guess."
            name="J. Whitfield"
            role="Certified Medical Coder"
          />
          <TestimonialCard
            quote="Our turnaround time from visit to billed encounter dropped noticeably in the first month."
            name="P. Nkemelu"
            role="Practice Administrator"
          />
        </div>
      </section>

      <CtaBanner
        title="Ready to see it on your own encounters?"
        subtitle="Request a demo and we will walk through the full workflow with your team."
        primaryHref="/contact"
        primaryLabel="Request a demo"
      />
    </>
  )
}
