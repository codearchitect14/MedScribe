import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useParams } from "react-router-dom"
import { Sparkles, CheckCircle2, Send } from "lucide-react"
import {
  createBillingRecord,
  decideCodeSuggestion,
  fetchEncounter,
  finalizeSoapNote,
  generateCarePlan,
  generateCodeSuggestions,
  generateSoapNote,
  reviewSoapNote,
  updateSoapNote,
} from "../../lib/endpoints"
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { EncounterStatusBadge, Badge } from "../../components/ui/Badge"
import { Tabs } from "../../components/ui/Tabs"
import { Textarea } from "../../components/ui/Input"
import { Alert } from "../../components/ui/Alert"
import { FullPageSpinner } from "../../components/ui/Spinner"
import { formatDateTime } from "../../lib/format"
import { useAuth } from "../../lib/AuthContext"
import type { BillingRecord, CarePlanContent, CodeSuggestion, SoapNote } from "../../types/api"

export function EncounterDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState("transcript")
  const canDecideCodes = user?.role === "coder" || user?.role === "admin" || user?.role === "super_admin"

  const { data, isLoading, error } = useQuery({
    queryKey: ["encounter", id],
    queryFn: () => fetchEncounter(id as string),
    enabled: Boolean(id),
  })

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["encounter", id] })
  }

  const generateNoteMutation = useMutation({ mutationFn: () => generateSoapNote(id as string), onSuccess: invalidate })
  const reviewMutation = useMutation({ mutationFn: () => reviewSoapNote(id as string), onSuccess: invalidate })
  const finalizeMutation = useMutation({ mutationFn: () => finalizeSoapNote(id as string), onSuccess: invalidate })
  const carePlanMutation = useMutation({ mutationFn: () => generateCarePlan(id as string), onSuccess: invalidate })
  const codesMutation = useMutation({ mutationFn: () => generateCodeSuggestions(id as string), onSuccess: invalidate })
  const billingMutation = useMutation({
    mutationFn: (codes: string[]) => createBillingRecord(id as string, { codes_applied: codes }),
    onSuccess: invalidate,
  })

  if (isLoading) return <FullPageSpinner />
  if (error || !data) return <Alert tone="error">Could not load this encounter.</Alert>

  const { encounter, soap_note, care_plan, code_suggestions, billing_record } = data
  let carePlanContent: CarePlanContent | null = null
  if (care_plan?.content) {
    try {
      carePlanContent = JSON.parse(care_plan.content)
    } catch {
      carePlanContent = null
    }
  }

  const anyMutationError =
    generateNoteMutation.error || reviewMutation.error || finalizeMutation.error || carePlanMutation.error || codesMutation.error || billingMutation.error

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Encounter {encounter.id.slice(0, 8)}</h1>
          <p className="mt-1 text-sm text-ink-500">Created {formatDateTime(encounter.created_at)}</p>
        </div>
        <EncounterStatusBadge status={encounter.status} />
      </div>

      {anyMutationError instanceof Error && <Alert tone="error">{anyMutationError.message}</Alert>}

      <Tabs
        tabs={[
          { key: "transcript", label: "Transcript" },
          { key: "note", label: "SOAP Note" },
          { key: "careplan", label: "Care Plan" },
          { key: "codes", label: "Codes & Billing" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "transcript" && (
        <Card>
          <CardBody>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
              {encounter.raw_transcript || "No transcript captured yet."}
            </p>
          </CardBody>
        </Card>
      )}

      {tab === "note" && (
        <SoapNoteTab
          encounterId={encounter.id}
          status={encounter.status}
          soapNote={soap_note}
          onGenerate={() => generateNoteMutation.mutate()}
          generating={generateNoteMutation.isPending}
          onReview={() => reviewMutation.mutate()}
          reviewing={reviewMutation.isPending}
          onFinalize={() => finalizeMutation.mutate()}
          finalizing={finalizeMutation.isPending}
          onInvalidate={invalidate}
        />
      )}

      {tab === "careplan" && (
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Care plan</CardTitle>
            {encounter.status !== "transcribed" && encounter.status !== "recording" && soap_note && (
              <Button size="sm" onClick={() => carePlanMutation.mutate()} loading={carePlanMutation.isPending}>
                <Sparkles className="h-4 w-4" />
                {care_plan ? "Regenerate" : "Generate care plan"}
              </Button>
            )}
          </CardHeader>
          <CardBody>
            {carePlanContent ? (
              <div className="space-y-4 text-sm">
                <div>
                  <p className="font-semibold text-ink-900">Diagnosis summary</p>
                  <p className="mt-1 text-ink-600">{carePlanContent.diagnosis_summary}</p>
                </div>
                <CarePlanList title="Follow-up actions" items={carePlanContent.follow_up_actions} />
                <CarePlanList title="Medications (require clinician confirmation)" items={carePlanContent.medications} />
                <CarePlanList title="Patient education" items={carePlanContent.patient_education} />
                <div>
                  <p className="font-semibold text-ink-900">Next appointment</p>
                  <p className="mt-1 text-ink-600">{carePlanContent.next_appointment_guidance}</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-ink-400">No care plan generated yet.</p>
            )}
          </CardBody>
        </Card>
      )}

      {tab === "codes" && (
        <CodesTab
          encounterId={encounter.id}
          status={encounter.status}
          codes={code_suggestions}
          billingRecord={billing_record}
          canDecide={canDecideCodes}
          onGenerate={() => codesMutation.mutate()}
          generating={codesMutation.isPending}
          onDecide={(suggestionId, accepted) =>
            decideCodeSuggestion(encounter.id, suggestionId, accepted).then(invalidate)
          }
          onCreateBilling={(codes) => billingMutation.mutate(codes)}
          billingPending={billingMutation.isPending}
        />
      )}
    </div>
  )
}

function CarePlanList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <p className="font-semibold text-ink-900">{title}</p>
      <ul className="mt-1 list-inside list-disc space-y-1 text-ink-600">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function SoapNoteTab({
  encounterId,
  status,
  soapNote,
  onGenerate,
  generating,
  onReview,
  reviewing,
  onFinalize,
  finalizing,
  onInvalidate,
}: {
  encounterId: string
  status: string
  soapNote: SoapNote | null
  onGenerate: () => void
  generating: boolean
  onReview: () => void
  reviewing: boolean
  onFinalize: () => void
  finalizing: boolean
  onInvalidate: () => void
}) {
  const [fields, setFields] = useState({
    subjective: soapNote?.subjective ?? "",
    objective: soapNote?.objective ?? "",
    assessment: soapNote?.assessment ?? "",
    plan: soapNote?.plan ?? "",
  })
  const [dirty, setDirty] = useState(false)
  const isFinalized = soapNote?.status === "finalized"

  const saveMutation = useMutation({
    mutationFn: () => updateSoapNote(encounterId, fields),
    onSuccess: () => {
      setDirty(false)
      onInvalidate()
    },
  })

  if (!soapNote) {
    return (
      <Card>
        <CardBody className="text-center">
          <p className="mb-4 text-sm text-ink-500">No SOAP note has been generated for this encounter yet.</p>
          <Button onClick={onGenerate} loading={generating}>
            <Sparkles className="h-4 w-4" />
            Generate SOAP note
          </Button>
        </CardBody>
      </Card>
    )
  }

  function updateField(key: keyof typeof fields, value: string) {
    setFields((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>SOAP note</CardTitle>
        <Badge tone={isFinalized ? "success" : "warning"} className="capitalize">
          {soapNote.status}
        </Badge>
      </CardHeader>
      <CardBody className="space-y-4">
        {(["subjective", "objective", "assessment", "plan"] as const).map((key) => (
          <div key={key}>
            <p className="mb-1.5 text-sm font-medium capitalize text-ink-700">{key}</p>
            <Textarea
              value={fields[key] ?? ""}
              disabled={isFinalized}
              onChange={(e) => updateField(key, e.target.value)}
              rows={3}
            />
          </div>
        ))}

        <div className="flex flex-wrap gap-3 pt-2">
          {!isFinalized && dirty && (
            <Button variant="secondary" onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
              Save changes
            </Button>
          )}
          {status === "note_generated" && (
            <Button onClick={onReview} loading={reviewing}>
              Move to review
            </Button>
          )}
          {status === "under_review" && (
            <Button onClick={onFinalize} loading={finalizing}>
              <CheckCircle2 className="h-4 w-4" />
              Finalize note
            </Button>
          )}
          {status !== "transcribed" && status !== "recording" && !isFinalized && (
            <Button variant="ghost" onClick={onGenerate} loading={generating}>
              Regenerate
            </Button>
          )}
        </div>
      </CardBody>
    </Card>
  )
}

function CodesTab({
  encounterId: _encounterId,
  status,
  codes,
  billingRecord,
  canDecide,
  onGenerate,
  generating,
  onDecide,
  onCreateBilling,
  billingPending,
}: {
  encounterId: string
  status: string
  codes: CodeSuggestion[]
  billingRecord: BillingRecord | null
  canDecide: boolean
  onGenerate: () => void
  generating: boolean
  onDecide: (suggestionId: string, accepted: boolean) => void
  onCreateBilling: (codes: string[]) => void
  billingPending: boolean
}) {
  if (status === "transcribed" || status === "recording" || status === "note_generated" || status === "under_review") {
    return (
      <Card>
        <CardBody className="text-center text-sm text-ink-400">
          The note must be finalized before generating code suggestions.
        </CardBody>
      </Card>
    )
  }

  const acceptedCodes = codes.filter((c) => c.accepted).map((c) => c.code)

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Code suggestions</CardTitle>
          {status === "finalized" && (
            <Button size="sm" onClick={onGenerate} loading={generating}>
              <Sparkles className="h-4 w-4" />
              Generate codes
            </Button>
          )}
        </CardHeader>
        <CardBody className="p-0">
          {codes.length === 0 ? (
            <p className="px-6 py-8 text-center text-sm text-ink-400">No code suggestions yet.</p>
          ) : (
            <ul className="divide-y divide-ink-100">
              {codes.map((code) => (
                <li key={code.id} className="flex items-center justify-between gap-4 px-6 py-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-ink-900">{code.code}</span>
                      <Badge tone="brand">{code.code_type.toUpperCase()}</Badge>
                      {code.confidence_score !== null && (
                        <span className="text-xs text-ink-400">
                          {Math.round(code.confidence_score * 100)}% confidence
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 truncate text-sm text-ink-500">{code.description}</p>
                  </div>
                  {canDecide ? (
                    <div className="flex shrink-0 gap-2">
                      <Button
                        size="sm"
                        variant={code.accepted === true ? "primary" : "secondary"}
                        onClick={() => onDecide(code.id, true)}
                      >
                        Accept
                      </Button>
                      <Button
                        size="sm"
                        variant={code.accepted === false ? "danger" : "secondary"}
                        onClick={() => onDecide(code.id, false)}
                      >
                        Reject
                      </Button>
                    </div>
                  ) : (
                    code.accepted !== null && (
                      <Badge tone={code.accepted ? "success" : "danger"}>
                        {code.accepted ? "Accepted" : "Rejected"}
                      </Badge>
                    )
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Billing</CardTitle>
        </CardHeader>
        <CardBody>
          {billingRecord ? (
            <div className="space-y-2 text-sm">
              <p>
                <span className="font-medium text-ink-700">Status: </span>
                <Badge tone="brand" className="capitalize">
                  {billingRecord.status}
                </Badge>
              </p>
              <p>
                <span className="font-medium text-ink-700">Codes applied: </span>
                {billingRecord.codes_applied.join(", ") || "—"}
              </p>
              {billingRecord.estimated_reimbursement !== null && (
                <p>
                  <span className="font-medium text-ink-700">Estimated reimbursement: </span>$
                  {billingRecord.estimated_reimbursement.toFixed(2)}
                </p>
              )}
            </div>
          ) : status === "coded" && canDecide ? (
            <div>
              <p className="mb-3 text-sm text-ink-500">
                Create a billing record from the {acceptedCodes.length} accepted code
                {acceptedCodes.length === 1 ? "" : "s"}.
              </p>
              <Button
                disabled={acceptedCodes.length === 0}
                loading={billingPending}
                onClick={() => onCreateBilling(acceptedCodes)}
              >
                <Send className="h-4 w-4" />
                Create billing record
              </Button>
            </div>
          ) : (
            <p className="text-sm text-ink-400">No billing record yet.</p>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
