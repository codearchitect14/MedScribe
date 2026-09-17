import { Check } from "lucide-react"
import { Link } from "react-router-dom"
import { Eyebrow, CtaBanner } from "../../components/public/Marketing"
import { buttonClass } from "../../components/ui/Button"
import clsx from "clsx"

const tiers = [
  {
    name: "Starter",
    price: "$0",
    period: "for a single clinician",
    description: "Everything you need to try ambient documentation on real encounters.",
    features: [
      "Up to 1 clinician seat",
      "Live, upload, and text transcript ingestion",
      "SOAP note and care plan generation",
      "ICD-10/HCPCS coding suggestions",
    ],
    cta: "Get started",
    highlighted: false,
  },
  {
    name: "Professional",
    price: "$149",
    period: "per clinician / month",
    description: "For multi-provider clinics that need coding review and analytics.",
    features: [
      "Unlimited clinician and coder seats",
      "Shared coding review queue",
      "Revenue and productivity analytics",
      "CSV/Excel export",
      "Priority support",
    ],
    cta: "Start free trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "for health systems",
    description: "Custom deployment, compliance review, and integration support.",
    features: [
      "Dedicated deployment and SLAs",
      "Custom retention and compliance review",
      "SSO and advanced audit exports",
      "Dedicated implementation manager",
    ],
    cta: "Contact sales",
    highlighted: false,
  },
]

export function PricingPage() {
  return (
    <>
      <section className="section py-16 text-center sm:py-24">
        <Eyebrow>Pricing</Eyebrow>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          Simple pricing that scales with your practice
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-500">
          Illustrative pricing for this reference build - the underlying LLM usage runs on free provider tiers,
          so these tiers reflect a real business model, not a technical constraint.
        </p>
      </section>

      <section className="section grid gap-8 pb-20 lg:grid-cols-3">
        {tiers.map((tier) => (
          <div
            key={tier.name}
            className={clsx(
              "flex flex-col rounded-2xl border p-8 shadow-sm",
              tier.highlighted ? "border-brand-600 bg-brand-700 text-white shadow-lg" : "border-ink-100 bg-white"
            )}
          >
            <h2 className={clsx("text-lg font-bold", tier.highlighted ? "text-white" : "text-ink-900")}>
              {tier.name}
            </h2>
            <p className={clsx("mt-4 text-4xl font-bold", tier.highlighted ? "text-white" : "text-ink-900")}>
              {tier.price}
            </p>
            <p className={clsx("text-sm", tier.highlighted ? "text-brand-100" : "text-ink-500")}>{tier.period}</p>
            <p className={clsx("mt-4 text-sm", tier.highlighted ? "text-brand-100" : "text-ink-500")}>
              {tier.description}
            </p>
            <ul className="mt-6 flex-1 space-y-3">
              {tier.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm">
                  <Check className={clsx("mt-0.5 h-4 w-4 shrink-0", tier.highlighted ? "text-white" : "text-brand-600")} />
                  <span className={tier.highlighted ? "text-white" : "text-ink-700"}>{f}</span>
                </li>
              ))}
            </ul>
            <Link
              to="/contact"
              className={clsx(
                "mt-8 text-center",
                buttonClass(tier.highlighted ? "secondary" : "primary", "md", tier.highlighted ? "!bg-white !text-brand-700" : "")
              )}
            >
              {tier.cta}
            </Link>
          </div>
        ))}
      </section>

      <CtaBanner
        title="Need something in between?"
        subtitle="We can tailor a plan to your seat count and compliance requirements."
        primaryHref="/contact"
        primaryLabel="Contact sales"
      />
    </>
  )
}
