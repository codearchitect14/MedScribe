import { apiRequest, buildQuery } from "./api"
import { API_BASE_URL } from "./config"
import { getAccessToken } from "./authStore"
import type {
  AccessTokenResponse,
  AnalyticsSeries,
  BillingRecord,
  CodeSuggestion,
  Encounter,
  EncounterDetail,
  EncounterStatus,
  Organization,
  Page,
  Patient,
  ReimbursementRate,
  RollupType,
  SoapNote,
  User,
  UserRole,
} from "../types/api"

// ---- Auth ----

export async function login(email: string, password: string): Promise<AccessTokenResponse> {
  const form = new URLSearchParams()
  form.set("username", email)
  form.set("password", password)
  return apiRequest<AccessTokenResponse>("/auth/login", {
    method: "POST",
    isForm: true,
    body: form,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    skipAuthRetry: true,
  })
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" })
}

export function fetchMe(): Promise<User> {
  return apiRequest<User>("/auth/me")
}

export function requestPasswordReset(email: string): Promise<void> {
  return apiRequest<void>("/auth/password-reset/request", { method: "POST", body: { email } })
}

// ---- Organizations ----

export function fetchMyOrganization(): Promise<Organization> {
  return apiRequest<Organization>("/organizations/me")
}

export function updateMyOrganization(name: string): Promise<Organization> {
  return apiRequest<Organization>("/organizations/me", { method: "PATCH", body: { name } })
}

// ---- Users ----

export function listUsers(params: { role?: UserRole; is_active?: boolean; page?: number } = {}) {
  return apiRequest<Page<User>>(`/users${buildQuery(params)}`)
}

export function inviteUser(payload: {
  email: string
  full_name: string
  role: UserRole
  temporary_password: string
}): Promise<User> {
  return apiRequest<User>("/users", { method: "POST", body: payload })
}

export function changeUserRole(userId: string, role: UserRole): Promise<User> {
  return apiRequest<User>(`/users/${userId}/role`, { method: "PATCH", body: { role } })
}

export function deactivateUser(userId: string): Promise<User> {
  return apiRequest<User>(`/users/${userId}/deactivate`, { method: "PATCH" })
}

// ---- Patients ----

export function listPatients(params: { page?: number; page_size?: number } = {}) {
  return apiRequest<Page<Patient>>(`/patients${buildQuery(params)}`)
}

export function createPatient(payload: {
  first_name: string
  last_name: string
  date_of_birth?: string | null
  sex?: string | null
}): Promise<Patient> {
  return apiRequest<Patient>("/patients", { method: "POST", body: payload })
}

export function fetchPatient(id: string): Promise<Patient> {
  return apiRequest<Patient>(`/patients/${id}`)
}

// ---- Encounters ----

export function listEncounters(
  params: { status?: EncounterStatus; patient_id?: string; page?: number; page_size?: number } = {}
) {
  return apiRequest<Page<Encounter>>(`/encounters${buildQuery(params)}`)
}

export function fetchEncounter(id: string): Promise<EncounterDetail> {
  return apiRequest<EncounterDetail>(`/encounters/${id}`)
}

export function createEncounter(payload: { patient_id: string; raw_transcript: string }): Promise<Encounter> {
  return apiRequest<Encounter>("/encounters", { method: "POST", body: payload })
}

export function createLiveEncounter(payload: { patient_id: string }): Promise<Encounter> {
  return apiRequest<Encounter>("/encounters/live", { method: "POST", body: payload })
}

export async function createEncounterFromAudio(patientId: string, file: File): Promise<Encounter> {
  const form = new FormData()
  form.set("patient_id", patientId)
  form.set("audio", file)
  return apiRequest<Encounter>("/encounters/audio", { method: "POST", isForm: true, body: form })
}

export function generateSoapNote(encounterId: string): Promise<SoapNote> {
  return apiRequest<SoapNote>(`/encounters/${encounterId}/soap-note`, { method: "POST" })
}

export function updateSoapNote(
  encounterId: string,
  payload: Partial<Pick<SoapNote, "subjective" | "objective" | "assessment" | "plan">>
): Promise<SoapNote> {
  return apiRequest<SoapNote>(`/encounters/${encounterId}/soap-note`, { method: "PATCH", body: payload })
}

export function reviewSoapNote(encounterId: string): Promise<SoapNote> {
  return apiRequest<SoapNote>(`/encounters/${encounterId}/soap-note/review`, { method: "POST" })
}

export function finalizeSoapNote(encounterId: string): Promise<SoapNote> {
  return apiRequest<SoapNote>(`/encounters/${encounterId}/soap-note/finalize`, { method: "POST" })
}

export function generateCarePlan(encounterId: string) {
  return apiRequest(`/encounters/${encounterId}/care-plan`, { method: "POST" })
}

export function generateCodeSuggestions(encounterId: string): Promise<CodeSuggestion[]> {
  return apiRequest<CodeSuggestion[]>(`/encounters/${encounterId}/codes`, { method: "POST" })
}

export function decideCodeSuggestion(
  encounterId: string,
  suggestionId: string,
  accepted: boolean
): Promise<CodeSuggestion> {
  return apiRequest<CodeSuggestion>(`/encounters/${encounterId}/codes/${suggestionId}`, {
    method: "PATCH",
    body: { accepted },
  })
}

export function createBillingRecord(
  encounterId: string,
  payload: { codes_applied: string[]; estimated_reimbursement?: number; payer?: string }
): Promise<BillingRecord> {
  return apiRequest<BillingRecord>(`/encounters/${encounterId}/billing-record`, {
    method: "POST",
    body: payload,
  })
}

// ---- Reimbursement rates ----

export function listReimbursementRates(page = 1) {
  return apiRequest<Page<ReimbursementRate>>(`/reimbursement-rates${buildQuery({ page, page_size: 100 })}`)
}

export function upsertReimbursementRate(payload: {
  code_type: "icd10" | "hcpcs"
  code: string
  rate: number
}): Promise<ReimbursementRate> {
  return apiRequest<ReimbursementRate>("/reimbursement-rates", { method: "PUT", body: payload })
}

export function deleteReimbursementRate(id: string): Promise<void> {
  return apiRequest<void>(`/reimbursement-rates/${id}`, { method: "DELETE" })
}

// ---- Analytics ----

export function triggerRollup(period?: string): Promise<{ period: string; rollup_types: string[] }> {
  return apiRequest("/analytics/rollup", { method: "POST", body: { period: period ?? null } })
}

export function fetchAnalyticsSeries(
  rollupType: RollupType,
  startDate: string,
  endDate: string
): Promise<AnalyticsSeries> {
  return apiRequest<AnalyticsSeries>(
    `/analytics/${rollupType}${buildQuery({ start_date: startDate, end_date: endDate })}`
  )
}

export function analyticsExportUrl(rollupType: RollupType, startDate: string, endDate: string, format: "csv" | "xlsx") {
  const qs = buildQuery({ start_date: startDate, end_date: endDate, format })
  return `${API_BASE_URL}/analytics/${rollupType}/export${qs}`
}

export async function downloadAnalyticsExport(
  rollupType: RollupType,
  startDate: string,
  endDate: string,
  format: "csv" | "xlsx"
) {
  const token = getAccessToken()
  const response = await fetch(analyticsExportUrl(rollupType, startDate, endDate, format), {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `${rollupType}_${startDate}_${endDate}.${format}`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
