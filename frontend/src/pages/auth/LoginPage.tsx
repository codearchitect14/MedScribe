import { useState, type FormEvent } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { Logo } from "../../components/Logo"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label } from "../../components/ui/Input"
import { Alert } from "../../components/ui/Alert"
import { useAuth } from "../../lib/AuthContext"
import { ApiError } from "../../lib/api"

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const redirectTo = (location.state as { from?: string } | null)?.from ?? "/app"

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError("")
    setLoading(true)
    try {
      await login(email, password)
      navigate(redirectTo, { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(typeof err.detail === "string" ? err.detail : "Incorrect email or password.")
      } else {
        setError("Something went wrong. Please try again.")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink-50/60 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="rounded-2xl border border-ink-100 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-bold text-ink-900">Log in to your account</h1>
          <p className="mt-1 text-sm text-ink-500">Enter your credentials to access MedScribe AI.</p>

          <form onSubmit={handleSubmit} className="mt-6">
            {error && (
              <div className="mb-4">
                <Alert tone="error">{error}</Alert>
              </div>
            )}
            <FieldGroup>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </FieldGroup>
            <FieldGroup>
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <Link to="/forgot-password" className="text-xs font-medium text-brand-600 hover:text-brand-700">
                  Forgot password?
                </Link>
              </div>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </FieldGroup>
            <Button type="submit" className="w-full" loading={loading}>
              Log in
            </Button>
          </form>
        </div>
        <p className="mt-6 text-center text-sm text-ink-500">
          <Link to="/" className="font-medium text-ink-700 hover:text-ink-900">
            &larr; Back to the homepage
          </Link>
        </p>
      </div>
    </div>
  )
}
