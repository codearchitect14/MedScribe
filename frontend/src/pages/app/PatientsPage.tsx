import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Plus, X } from "lucide-react"
import { createPatient, listPatients } from "../../lib/endpoints"
import { Card, CardBody } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label, Select } from "../../components/ui/Input"
import { FullPageSpinner } from "../../components/ui/Spinner"

export function PatientsPage() {
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["patients", page],
    queryFn: () => listPatients({ page, page_size: 10 }),
  })

  const createMutation = useMutation({
    mutationFn: createPatient,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["patients"] })
      setShowForm(false)
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    createMutation.mutate({
      first_name: String(form.get("first_name") || ""),
      last_name: String(form.get("last_name") || ""),
      date_of_birth: (form.get("date_of_birth") as string) || null,
      sex: (form.get("sex") as string) || null,
    })
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Patients</h1>
          <p className="mt-1 text-sm text-ink-500">{data?.total ?? 0} patients in your organization</p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showForm ? "Cancel" : "Add patient"}
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardBody>
            <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <FieldGroup>
                <Label htmlFor="first_name">First name</Label>
                <Input id="first_name" name="first_name" required />
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="last_name">Last name</Label>
                <Input id="last_name" name="last_name" required />
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="date_of_birth">Date of birth</Label>
                <Input id="date_of_birth" name="date_of_birth" type="date" />
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="sex">Sex</Label>
                <Select id="sex" name="sex" defaultValue="">
                  <option value="">Unspecified</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </Select>
              </FieldGroup>
              <div className="sm:col-span-2 lg:col-span-4">
                <Button type="submit" loading={createMutation.isPending}>
                  Save patient
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      {isLoading ? (
        <FullPageSpinner />
      ) : (
        <Card>
          <CardBody className="p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-400">
                <tr>
                  <th className="px-6 py-3 font-medium">Name</th>
                  <th className="px-6 py-3 font-medium">Date of birth</th>
                  <th className="px-6 py-3 font-medium">Sex</th>
                  <th className="px-6 py-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-100">
                {data?.items.map((patient) => (
                  <tr key={patient.id} className="hover:bg-ink-50">
                    <td className="px-6 py-3.5 font-medium text-ink-900">
                      {patient.first_name} {patient.last_name}
                    </td>
                    <td className="px-6 py-3.5 text-ink-500">{patient.date_of_birth ?? "—"}</td>
                    <td className="px-6 py-3.5 capitalize text-ink-500">{patient.sex ?? "—"}</td>
                    <td className="px-6 py-3.5 text-right">
                      <Link
                        to={`/app/encounters/new?patient=${patient.id}`}
                        className="text-sm font-medium text-brand-600 hover:text-brand-700"
                      >
                        New encounter
                      </Link>
                    </td>
                  </tr>
                ))}
                {data?.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-10 text-center text-ink-400">
                      No patients yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span className="text-sm text-ink-500">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
