import { useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { Logo } from "../../components/Logo"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label } from "../../components/ui/Input"
import { Alert } from "../../components/ui/Alert"
import { requestPasswordReset } from "../../lib/endpoints"

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setLoading(true)
    try {
      await requestPasswordReset(email)
    } finally {
      setLoading(false)
      // The API always returns 204 regardless of whether the email is
      // registered, so the UI never reveals which emails have accounts.
      setSubmitted(true)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50/60 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="rounded-2xl border border-ink-100 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-bold text-ink-900">Reset your password</h1>
          <p className="mt-1 text-sm text-ink-500">
            Enter your email and, if it matches an account, we will send a reset link.
          </p>

          {submitted ? (
            <div className="mt-6">
              <Alert tone="success">If that email is registered, a reset link is on its way.</Alert>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6">
              <FieldGroup>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </FieldGroup>
              <Button type="submit" className="w-full" loading={loading}>
                Send reset link
              </Button>
            </form>
          )}
        </div>
        <p className="mt-6 text-center text-sm text-ink-500">
          <Link to="/login" className="font-medium text-ink-700 hover:text-ink-900">
            &larr; Back to login
          </Link>
        </p>
      </div>
    </div>
  )
}
