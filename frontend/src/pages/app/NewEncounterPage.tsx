import { useEffect, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useSearchParams } from "react-router-dom"
import { Mic, Upload, FileText, Square, Pause, Play, Loader2 } from "lucide-react"
import clsx from "clsx"
import {
  createEncounter,
  createEncounterFromAudio,
  createLiveEncounter,
  createPatient,
  listPatients,
} from "../../lib/endpoints"
import { useLiveRecorder } from "../../lib/useLiveRecorder"
import { Card, CardBody } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { FieldGroup, Input, Label, Select, Textarea } from "../../components/ui/Input"
import { Alert } from "../../components/ui/Alert"

type Mode = "text" | "upload" | "live"

export function NewEncounterPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()

  const [patientId, setPatientId] = useState(searchParams.get("patient") ?? "")
  const [creatingPatient, setCreatingPatient] = useState(false)
  const [mode, setMode] = useState<Mode>("text")
  const [transcript, setTranscript] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [liveEncounterId, setLiveEncounterId] = useState<string | null>(null)

  const { data: patients } = useQuery({
    queryKey: ["patients", "all-for-select"],
    queryFn: () => listPatients({ page: 1, page_size: 100 }),
  })

  const createPatientMutation = useMutation({
    mutationFn: createPatient,
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] })
      setPatientId(patient.id)
      setCreatingPatient(false)
    },
  })

  const textMutation = useMutation({
    mutationFn: () => createEncounter({ patient_id: patientId, raw_transcript: transcript }),
    onSuccess: (encounter) => navigate(`/app/encounters/${encounter.id}`),
  })

  const uploadMutation = useMutation({
    mutationFn: () => createEncounterFromAudio(patientId, file as File),
    onSuccess: (encounter) => navigate(`/app/encounters/${encounter.id}`),
  })

  const liveEncounterMutation = useMutation({
    mutationFn: () => createLiveEncounter({ patient_id: patientId }),
    onSuccess: (encounter) => setLiveEncounterId(encounter.id),
  })

  const recorder = useLiveRecorder(liveEncounterId)

  useEffect(() => {
    if (recorder.status === "stopped" && liveEncounterId) {
      navigate(`/app/encounters/${liveEncounterId}`)
    }
  }, [recorder.status, liveEncounterId, navigate])

  const hasPatient = Boolean(patientId)

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink-900">New encounter</h1>
        <p className="mt-1 text-sm text-ink-500">Select a patient, then capture the encounter.</p>
      </div>

      <Card>
        <CardBody>
          <Label htmlFor="patient">Patient</Label>
          {!creatingPatient ? (
            <div className="flex gap-2">
              <Select id="patient" value={patientId} onChange={(e) => setPatientId(e.target.value)} className="flex-1">
                <option value="">Select a patient&hellip;</option>
                {patients?.items.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.first_name} {p.last_name}
                  </option>
                ))}
              </Select>
              <Button type="button" variant="secondary" onClick={() => setCreatingPatient(true)}>
                New patient
              </Button>
            </div>
          ) : (
            <NewPatientInlineForm
              onCancel={() => setCreatingPatient(false)}
              onSubmit={(payload) => createPatientMutation.mutate(payload)}
              loading={createPatientMutation.isPending}
            />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <div className="grid grid-cols-3 gap-2 rounded-lg bg-ink-50 p-1">
            {[
              { key: "text" as Mode, label: "Paste text", icon: FileText },
              { key: "upload" as Mode, label: "Upload audio", icon: Upload },
              { key: "live" as Mode, label: "Live record", icon: Mic },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setMode(tab.key)}
                disabled={recorder.status !== "idle" && recorder.status !== "stopped"}
                className={clsx(
                  "flex items-center justify-center gap-2 rounded-md py-2 text-sm font-medium transition-colors",
                  mode === tab.key ? "bg-white text-brand-700 shadow-sm" : "text-ink-500 hover:text-ink-800"
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>

          <div className="mt-6">
            {mode === "text" && (
              <div>
                <FieldGroup>
                  <Label htmlFor="transcript">Transcript</Label>
                  <Textarea
                    id="transcript"
                    rows={10}
                    placeholder="Doctor: How have you been feeling? Patient: ..."
                    value={transcript}
                    onChange={(e) => setTranscript(e.target.value)}
                  />
                </FieldGroup>
                {textMutation.isError && <ErrorAlert error={textMutation.error} />}
                <Button
                  disabled={!hasPatient || !transcript.trim()}
                  loading={textMutation.isPending}
                  onClick={() => textMutation.mutate()}
                >
                  Continue
                </Button>
              </div>
            )}

            {mode === "upload" && (
              <div>
                <FieldGroup>
                  <Label htmlFor="audio-file">Audio file</Label>
                  <input
                    id="audio-file"
                    type="file"
                    accept="audio/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="block w-full text-sm text-ink-600 file:mr-4 file:rounded-lg file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-brand-700 hover:file:bg-brand-100"
                  />
                </FieldGroup>
                {uploadMutation.isError && <ErrorAlert error={uploadMutation.error} />}
                <Button disabled={!hasPatient || !file} loading={uploadMutation.isPending} onClick={() => uploadMutation.mutate()}>
                  Transcribe and continue
                </Button>
              </div>
            )}

            {mode === "live" && (
              <LiveRecordingPanel
                hasPatient={hasPatient}
                liveEncounterId={liveEncounterId}
                onCreateEncounter={() => liveEncounterMutation.mutate()}
                creating={liveEncounterMutation.isPending}
                recorder={recorder}
              />
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

function ErrorAlert({ error }: { error: unknown }) {
  return (
    <div className="mb-4">
      <Alert tone="error">{error instanceof Error ? error.message : "Something went wrong."}</Alert>
    </div>
  )
}

function NewPatientInlineForm({
  onCancel,
  onSubmit,
  loading,
}: {
  onCancel: () => void
  onSubmit: (payload: { first_name: string; last_name: string }) => void
  loading: boolean
}) {
  const [firstName, setFirstName] = useState("")
  const [lastName, setLastName] = useState("")
  return (
    <div className="rounded-lg border border-ink-100 bg-ink-50/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Input placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
        <Input placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} />
      </div>
      <div className="mt-3 flex gap-2">
        <Button
          size="sm"
          disabled={!firstName || !lastName}
          loading={loading}
          onClick={() => onSubmit({ first_name: firstName, last_name: lastName })}
        >
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function LiveRecordingPanel({
  hasPatient,
  liveEncounterId,
  onCreateEncounter,
  creating,
  recorder,
}: {
  hasPatient: boolean
  liveEncounterId: string | null
  onCreateEncounter: () => void
  creating: boolean
  recorder: ReturnType<typeof useLiveRecorder>
}) {
  if (!liveEncounterId) {
    return (
      <div className="text-center">
        <p className="mb-4 text-sm text-ink-500">
          This will request microphone access and stream audio for live transcription. Make sure you have
          patient consent to record before starting.
        </p>
        <Button disabled={!hasPatient} loading={creating} onClick={onCreateEncounter} size="lg">
          <Mic className="h-4 w-4" />
          Start recording
        </Button>
      </div>
    )
  }

  const isConnecting = recorder.status === "connecting" || recorder.status === "queued"
  const isActive = recorder.status === "recording" || recorder.status === "paused"

  return (
    <div>
      {recorder.status === "idle" && (
        <div className="text-center">
          <Button size="lg" onClick={recorder.start}>
            <Mic className="h-4 w-4" />
            Begin capture
          </Button>
        </div>
      )}

      {isConnecting && (
        <div className="flex items-center justify-center gap-2 py-6 text-sm text-ink-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          {recorder.status === "queued" ? "Waiting for a transcription slot…" : "Connecting…"}
        </div>
      )}

      {(isActive || recorder.status === "stopping") && (
        <div>
          <div className="mb-4 flex items-center justify-center gap-3">
            <span className="relative flex h-3 w-3">
              {recorder.status === "recording" && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose-400 opacity-75" />
              )}
              <span
                className={clsx(
                  "relative inline-flex h-3 w-3 rounded-full",
                  recorder.status === "recording" ? "bg-rose-500" : "bg-amber-500"
                )}
              />
            </span>
            <span className="text-sm font-medium text-ink-700">
              {recorder.status === "paused" ? "Paused" : "Recording live"}
            </span>
          </div>

          <div className="min-h-32 rounded-lg border border-ink-100 bg-ink-50/60 p-4 text-sm leading-relaxed">
            {recorder.finalSegments.map((segment, i) => (
              <span key={i} className="text-ink-800">
                {segment}{" "}
              </span>
            ))}
            <span className="text-ink-400">{recorder.partialText}</span>
            {recorder.finalSegments.length === 0 && !recorder.partialText && (
              <span className="text-ink-400">Listening&hellip;</span>
            )}
          </div>

          {recorder.errorMessage && (
            <div className="mt-3">
              <Alert tone="error">{recorder.errorMessage}</Alert>
            </div>
          )}

          <div className="mt-4 flex justify-center gap-3">
            <Button
              variant="secondary"
              onClick={() => recorder.setPaused(recorder.status !== "paused")}
              disabled={recorder.status === "stopping"}
            >
              {recorder.status === "paused" ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
              {recorder.status === "paused" ? "Resume" : "Pause"}
            </Button>
            <Button variant="danger" onClick={recorder.stop} loading={recorder.status === "stopping"}>
              <Square className="h-4 w-4" />
              Stop and continue
            </Button>
          </div>
        </div>
      )}

      {recorder.status === "error" && <Alert tone="error">{recorder.errorMessage}</Alert>}
    </div>
  )
}
