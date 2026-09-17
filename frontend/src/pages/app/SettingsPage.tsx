import { useState, type FormEvent } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus, Trash2 } from "lucide-react"
import {
  changeUserRole,
  deactivateUser,
  fetchMyOrganization,
  inviteUser,
  listReimbursementRates,
  listUsers,
  updateMyOrganization,
  upsertReimbursementRate,
  deleteReimbursementRate,
} from "../../lib/endpoints"
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label, Select } from "../../components/ui/Input"
import { Badge } from "../../components/ui/Badge"
import { Tabs } from "../../components/ui/Tabs"
import { Alert } from "../../components/ui/Alert"
import type { UserRole } from "../../types/api"

export function SettingsPage() {
  const [tab, setTab] = useState("organization")

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">Settings</h1>
        <p className="mt-1 text-sm text-ink-500">Manage your organization, team, and billing configuration.</p>
      </div>

      <Tabs
        tabs={[
          { key: "organization", label: "Organization" },
          { key: "users", label: "Users" },
          { key: "rates", label: "Reimbursement rates" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "organization" && <OrganizationSection />}
      {tab === "users" && <UsersSection />}
      {tab === "rates" && <ReimbursementRatesSection />}
    </div>
  )
}

function OrganizationSection() {
  const queryClient = useQueryClient()
  const { data: org } = useQuery({ queryKey: ["organization", "me"], queryFn: fetchMyOrganization })
  const [name, setName] = useState("")

  const mutation = useMutation({
    mutationFn: () => updateMyOrganization(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["organization", "me"] }),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization profile</CardTitle>
      </CardHeader>
      <CardBody>
        <FieldGroup>
          <Label htmlFor="org-name">Organization name</Label>
          <Input id="org-name" placeholder={org?.name} value={name} onChange={(e) => setName(e.target.value)} />
        </FieldGroup>
        <Button disabled={!name.trim()} loading={mutation.isPending} onClick={() => mutation.mutate()}>
          Save changes
        </Button>
      </CardBody>
    </Card>
  )
}

function UsersSection() {
  const queryClient = useQueryClient()
  const [showInvite, setShowInvite] = useState(false)
  const { data } = useQuery({ queryKey: ["users"], queryFn: () => listUsers({ page: 1 }) })

  const inviteMutation = useMutation({
    mutationFn: inviteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
      setShowInvite(false)
    },
  })
  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) => changeUserRole(userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  })
  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  })

  function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    inviteMutation.mutate({
      email: String(form.get("email")),
      full_name: String(form.get("full_name")),
      role: form.get("role") as UserRole,
      temporary_password: String(form.get("temporary_password")),
    })
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowInvite((v) => !v)}>
          <Plus className="h-4 w-4" />
          Invite user
        </Button>
      </div>

      {showInvite && (
        <Card>
          <CardBody>
            {inviteMutation.isError && (
              <div className="mb-4">
                <Alert tone="error">
                  {inviteMutation.error instanceof Error ? inviteMutation.error.message : "Could not invite user."}
                </Alert>
              </div>
            )}
            <form onSubmit={handleInvite} className="grid gap-4 sm:grid-cols-2">
              <FieldGroup>
                <Label htmlFor="full_name">Full name</Label>
                <Input id="full_name" name="full_name" required />
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="email">Email</Label>
                <Input id="email" name="email" type="email" required />
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="role">Role</Label>
                <Select id="role" name="role" defaultValue="clinician">
                  <option value="clinician">Clinician</option>
                  <option value="coder">Coder</option>
                  <option value="admin">Admin</option>
                </Select>
              </FieldGroup>
              <FieldGroup>
                <Label htmlFor="temporary_password">Temporary password</Label>
                <Input id="temporary_password" name="temporary_password" type="text" minLength={8} required />
              </FieldGroup>
              <div className="sm:col-span-2">
                <Button type="submit" loading={inviteMutation.isPending}>
                  Send invite
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody className="p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-400">
              <tr>
                <th className="px-6 py-3 font-medium">Name</th>
                <th className="px-6 py-3 font-medium">Email</th>
                <th className="px-6 py-3 font-medium">Role</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {data?.items.map((user) => (
                <tr key={user.id}>
                  <td className="px-6 py-3 font-medium text-ink-900">{user.full_name}</td>
                  <td className="px-6 py-3 text-ink-500">{user.email}</td>
                  <td className="px-6 py-3">
                    <Select
                      value={user.role}
                      onChange={(e) => roleMutation.mutate({ userId: user.id, role: e.target.value as UserRole })}
                      className="!w-auto py-1 text-xs"
                    >
                      <option value="clinician">Clinician</option>
                      <option value="coder">Coder</option>
                      <option value="admin">Admin</option>
                      <option value="super_admin">Super admin</option>
                    </Select>
                  </td>
                  <td className="px-6 py-3">
                    <Badge tone={user.is_active ? "success" : "neutral"}>
                      {user.is_active ? "Active" : "Deactivated"}
                    </Badge>
                  </td>
                  <td className="px-6 py-3 text-right">
                    {user.is_active && (
                      <button
                        onClick={() => deactivateMutation.mutate(user.id)}
                        className="text-xs font-medium text-rose-600 hover:text-rose-700"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  )
}

function ReimbursementRatesSection() {
  const queryClient = useQueryClient()
  const { data } = useQuery({ queryKey: ["reimbursement-rates"], queryFn: () => listReimbursementRates() })

  const upsertMutation = useMutation({
    mutationFn: upsertReimbursementRate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reimbursement-rates"] }),
  })
  const deleteMutation = useMutation({
    mutationFn: deleteReimbursementRate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reimbursement-rates"] }),
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    upsertMutation.mutate({
      code_type: form.get("code_type") as "icd10" | "hcpcs",
      code: String(form.get("code")),
      rate: Number(form.get("rate")),
    })
    event.currentTarget.reset()
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Add or update a rate</CardTitle>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-4">
            <FieldGroup>
              <Label htmlFor="code_type">Type</Label>
              <Select id="code_type" name="code_type" defaultValue="icd10">
                <option value="icd10">ICD-10</option>
                <option value="hcpcs">HCPCS</option>
              </Select>
            </FieldGroup>
            <FieldGroup>
              <Label htmlFor="code">Code</Label>
              <Input id="code" name="code" required placeholder="E11.9" />
            </FieldGroup>
            <FieldGroup>
              <Label htmlFor="rate">Rate (USD)</Label>
              <Input id="rate" name="rate" type="number" step="0.01" min="0" required />
            </FieldGroup>
            <div className="flex items-end">
              <Button type="submit" loading={upsertMutation.isPending} className="w-full">
                Save
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardBody className="p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-400">
              <tr>
                <th className="px-6 py-3 font-medium">Code</th>
                <th className="px-6 py-3 font-medium">Type</th>
                <th className="px-6 py-3 font-medium">Rate</th>
                <th className="px-6 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {data?.items.map((rate) => (
                <tr key={rate.id}>
                  <td className="px-6 py-3 font-mono font-medium text-ink-900">{rate.code}</td>
                  <td className="px-6 py-3">
                    <Badge tone="brand">{rate.code_type.toUpperCase()}</Badge>
                  </td>
                  <td className="px-6 py-3">${rate.rate.toFixed(2)}</td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => deleteMutation.mutate(rate.id)}
                      className="text-ink-400 hover:text-rose-600"
                      aria-label="Delete rate"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-10 text-center text-ink-400">
                    No rates configured yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  )
}
