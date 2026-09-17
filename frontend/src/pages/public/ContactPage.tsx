import { useState, type FormEvent } from "react"
import { Mail, MapPin, Phone } from "lucide-react"
import { Eyebrow } from "../../components/public/Marketing"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label, Textarea } from "../../components/ui/Input"
import { Alert } from "../../components/ui/Alert"
import { apiRequest } from "../../lib/api"

export function ContactPage() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [organization, setOrganization] = useState("")
  const [message, setMessage] = useState("")
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle")
  const [errorMessage, setErrorMessage] = useState("")

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setStatus("submitting")
    setErrorMessage("")
    try {
      await apiRequest("/contact", {
        method: "POST",
        body: { name, email, organization_name: organization || null, message },
        skipAuthRetry: true,
      })
      setStatus("success")
      setName("")
      setEmail("")
      setOrganization("")
      setMessage("")
    } catch (err) {
      setStatus("error")
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong. Please try again.")
    }
  }

  return (
    <section className="section grid gap-14 py-16 sm:py-24 lg:grid-cols-2">
      <div>
        <Eyebrow>Contact</Eyebrow>
        <h1 className="text-balance text-4xl font-bold tracking-tight text-ink-900 sm:text-5xl">
          Let&apos;s talk about your documentation workflow
        </h1>
        <p className="mt-6 text-lg text-ink-500">
          Tell us a bit about your practice and we will follow up with a demo tailored to your specialty and
          team size.
        </p>

        <div className="mt-10 space-y-5">
          <div className="flex items-center gap-3 text-sm text-ink-600">
            <Mail className="h-5 w-5 text-brand-600" />
            hello@medscribe.example
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-600">
            <Phone className="h-5 w-5 text-brand-600" />
            +1 (555) 010-0100
          </div>
          <div className="flex items-center gap-3 text-sm text-ink-600">
            <MapPin className="h-5 w-5 text-brand-600" />
            Remote-first, serving clinics across the US
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-ink-100 bg-white p-8 shadow-sm">
        {status === "success" ? (
          <Alert tone="success">Thanks for reaching out - we will be in touch shortly.</Alert>
        ) : (
          <form onSubmit={handleSubmit}>
            {status === "error" && (
              <div className="mb-4">
                <Alert tone="error">{errorMessage}</Alert>
              </div>
            )}
            <FieldGroup>
              <Label htmlFor="name">Full name</Label>
              <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
            </FieldGroup>
            <FieldGroup>
              <Label htmlFor="email">Work email</Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <Label htmlFor="organization">Organization</Label>
              <Input id="organization" value={organization} onChange={(e) => setOrganization(e.target.value)} />
            </FieldGroup>
            <FieldGroup>
              <Label htmlFor="message">How can we help?</Label>
              <Textarea
                id="message"
                required
                rows={5}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
              />
            </FieldGroup>
            <Button type="submit" className="w-full" loading={status === "submitting"}>
              Send message
            </Button>
          </form>
        )}
      </div>
    </section>
  )
}
