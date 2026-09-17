import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Mic, Plus, FileText, Tags } from "lucide-react"
import { useAuth } from "../../lib/AuthContext"
import { listEncounters } from "../../lib/endpoints"
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { EncounterStatusBadge } from "../../components/ui/Badge"
import { FullPageSpinner } from "../../components/ui/Spinner"
import { formatDateTime } from "../../lib/format"

export function DashboardPage() {
  const { user } = useAuth()
  const isReviewer = user?.role === "admin" || user?.role === "super_admin" || user?.role === "coder"

  const { data: myEncounters, isLoading } = useQuery({
    queryKey: ["encounters", "recent"],
    queryFn: () => listEncounters({ page: 1, page_size: 8 }),
  })

  const { data: codingQueue } = useQuery({
    queryKey: ["encounters", "coding-queue"],
    queryFn: () => listEncounters({ status: "coded", page: 1, page_size: 8 }),
    enabled: isReviewer,
  })

  if (isLoading) return <FullPageSpinner />

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Welcome back, {user?.full_name?.split(" ")[0]}</h1>
          <p className="mt-1 text-sm text-ink-500">
            {isReviewer ? "Here's what's happening across your organization." : "Here are your recent encounters."}
          </p>
        </div>
        <Link to="/app/encounters/new">
          <Button size="lg">
            <Plus className="h-4 w-4" />
            New encounter
          </Button>
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>{isReviewer ? "Recent encounters" : "Your recent encounters"}</CardTitle>
              <Link to="/app/patients" className="text-sm font-medium text-brand-600 hover:text-brand-700">
                View patients
              </Link>
            </CardHeader>
            <CardBody className="p-0">
              {myEncounters && myEncounters.items.length > 0 ? (
                <ul className="divide-y divide-ink-100">
                  {myEncounters.items.map((encounter) => (
                    <li key={encounter.id}>
                      <Link
                        to={`/app/encounters/${encounter.id}`}
                        className="flex items-center justify-between gap-4 px-6 py-4 transition-colors hover:bg-ink-50"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-ink-900">
                            Encounter {encounter.id.slice(0, 8)}
                          </p>
                          <p className="text-xs text-ink-400">{formatDateTime(encounter.created_at)}</p>
                        </div>
                        <EncounterStatusBadge status={encounter.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="px-6 py-10 text-center text-sm text-ink-400">
                  No encounters yet. Start your first one above.
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Quick actions</CardTitle>
            </CardHeader>
            <CardBody className="space-y-3">
              <Link
                to="/app/encounters/new"
                className="flex items-center gap-3 rounded-lg border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:bg-ink-50"
              >
                <Mic className="h-4 w-4 text-brand-600" /> Start a live recording
              </Link>
              <Link
                to="/app/encounters/new"
                className="flex items-center gap-3 rounded-lg border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:bg-ink-50"
              >
                <FileText className="h-4 w-4 text-brand-600" /> Paste a transcript
              </Link>
              {isReviewer && (
                <Link
                  to="/app/analytics"
                  className="flex items-center gap-3 rounded-lg border border-ink-100 px-4 py-3 text-sm font-medium text-ink-700 hover:bg-ink-50"
                >
                  <Tags className="h-4 w-4 text-brand-600" /> Review coding queue
                </Link>
              )}
            </CardBody>
          </Card>

          {isReviewer && codingQueue && (
            <Card>
              <CardHeader>
                <CardTitle>Coding review queue</CardTitle>
              </CardHeader>
              <CardBody className="p-0">
                {codingQueue.items.length > 0 ? (
                  <ul className="divide-y divide-ink-100">
                    {codingQueue.items.map((encounter) => (
                      <li key={encounter.id}>
                        <Link
                          to={`/app/encounters/${encounter.id}`}
                          className="flex items-center justify-between px-6 py-3 text-sm hover:bg-ink-50"
                        >
                          <span className="text-ink-700">Encounter {encounter.id.slice(0, 8)}</span>
                          <EncounterStatusBadge status={encounter.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="px-6 py-8 text-center text-sm text-ink-400">Queue is clear.</div>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
