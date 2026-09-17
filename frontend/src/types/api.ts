export type UserRole = "clinician" | "coder" | "admin" | "super_admin"

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  organization_id: string
  is_active: boolean
}

export interface Organization {
  id: string
  name: string
  is_active: boolean
  created_at: string
}

export interface Patient {
  id: string
  organization_id: string
  first_name: string
  last_name: string
  date_of_birth: string | null
  sex: string | null
  external_reference: string | null
}

export type EncounterStatus =
  | "recording"
  | "transcribed"
  | "note_generated"
  | "under_review"
  | "finalized"
  | "coded"
  | "billed"

export interface Encounter {
  id: string
  patient_id: string
  clinician_id: string
  organization_id: string
  status: EncounterStatus
  raw_transcript: string | null
  created_at: string
}

export type SoapNoteStatus = "draft" | "reviewed" | "finalized"

export interface SoapNote {
  id: string
  encounter_id: string
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  model_used: string | null
  tokens_used: number | null
  status: SoapNoteStatus
  generated_at: string
  reviewed_by: string | null
  reviewed_at: string | null
}

export interface CarePlan {
  id: string
  encounter_id: string
  content: string | null
  generated_at: string
  reviewed_by: string | null
  reviewed_at: string | null
}

export interface CarePlanContent {
  diagnosis_summary: string
  follow_up_actions: string[]
  medications: string[]
  patient_education: string[]
  next_appointment_guidance: string
}

export type CodeType = "icd10" | "hcpcs"

export interface CodeSuggestion {
  id: string
  encounter_id: string
  code_type: CodeType
  code: string
  description: string
  confidence_score: number | null
  accepted: boolean | null
}

export type BillingStatus = "pending" | "submitted" | "paid" | "denied"

export interface BillingRecord {
  id: string
  encounter_id: string
  codes_applied: string[]
  estimated_reimbursement: number | null
  billed_amount: number | null
  payer: string | null
  status: BillingStatus
  created_at: string
}

export interface EncounterDetail {
  encounter: Encounter
  soap_note: SoapNote | null
  care_plan: CarePlan | null
  code_suggestions: CodeSuggestion[]
  billing_record: BillingRecord | null
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ReimbursementRate {
  id: string
  organization_id: string
  code_type: CodeType
  code: string
  rate: number
  created_at: string
}

export type RollupType =
  | "encounter_volume"
  | "coding_mix"
  | "estimated_reimbursement"
  | "turnaround_time"
  | "llm_usage"
  | "clinician_productivity"

export interface Rollup {
  rollup_type: RollupType
  period: string
  dimensions: Record<string, unknown>[]
}

export interface AnalyticsSeries {
  rollup_type: RollupType
  start_date: string
  end_date: string
  rollups: Rollup[]
}

export interface AccessTokenResponse {
  access_token: string
  token_type: string
  expires_in_minutes: number
  csrf_token: string
}
