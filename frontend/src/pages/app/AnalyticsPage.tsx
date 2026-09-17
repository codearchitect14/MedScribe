import { useMemo, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts"
import { Download, RefreshCw, Users, Activity, Clock, DollarSign } from "lucide-react"
import { fetchAnalyticsSeries, downloadAnalyticsExport, triggerRollup } from "../../lib/endpoints"
import { Card, CardBody, CardHeader, CardTitle } from "../../components/ui/Card"
import { Button } from "../../components/ui/Button"
import { Input, Label } from "../../components/ui/Input"
import { StatTile } from "../../components/ui/StatTile"
import { FullPageSpinner } from "../../components/ui/Spinner"
import { formatCurrency } from "../../lib/format"
import type { RollupType } from "../../types/api"

const CHART_COLORS = ["#2f57f5", "#0fb4a5", "#e2921b", "#e0446b", "#8891a3", "#5480ff"]

function toISODate(date: Date) {
  return date.toISOString().slice(0, 10)
}

export function AnalyticsPage() {
  const [endDate, setEndDate] = useState(() => toISODate(new Date()))
  const [startDate, setStartDate] = useState(() => toISODate(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)))

  const volume = useQuery({
    queryKey: ["analytics", "encounter_volume", startDate, endDate],
    queryFn: () => fetchAnalyticsSeries("encounter_volume", startDate, endDate),
  })
  const codingMix = useQuery({
    queryKey: ["analytics", "coding_mix", startDate, endDate],
    queryFn: () => fetchAnalyticsSeries("coding_mix", startDate, endDate),
  })
  const reimbursement = useQuery({
    queryKey: ["analytics", "estimated_reimbursement", startDate, endDate],
    queryFn: () => fetchAnalyticsSeries("estimated_reimbursement", startDate, endDate),
  })
  const turnaround = useQuery({
    queryKey: ["analytics", "turnaround_time", startDate, endDate],
    queryFn: () => fetchAnalyticsSeries("turnaround_time", startDate, endDate),
  })
  const llmUsage = useQuery({
    queryKey: ["analytics", "llm_usage", startDate, endDate],
    queryFn: () => fetchAnalyticsSeries("llm_usage", startDate, endDate),
  })

  const rollupMutation = useMutation({ mutationFn: () => triggerRollup() })

  const volumeChartData = useMemo(() => {
    return (volume.data?.rollups ?? []).map((r) => {
      const total = r.dimensions.find((d) => d.clinician_id === null)
      return { date: r.period.slice(5), count: (total?.count as number) ?? 0 }
    })
  }, [volume.data])

  const codingMixData = useMemo(() => {
    const totals = new Map<string, number>()
    for (const rollup of codingMix.data?.rollups ?? []) {
      for (const dim of rollup.dimensions) {
        const key = `${dim.group}`
        totals.set(key, (totals.get(key) ?? 0) + (dim.count as number))
      }
    }
    return Array.from(totals.entries()).map(([name, value]) => ({ name, value }))
  }, [codingMix.data])

  const totalReimbursement = useMemo(() => {
    return (reimbursement.data?.rollups ?? []).reduce((sum, r) => {
      const row = r.dimensions[0]
      return sum + ((row?.estimated_reimbursement as number) ?? 0)
    }, 0)
  }, [reimbursement.data])

  const avgTurnaround = useMemo(() => {
    const rows = (turnaround.data?.rollups ?? [])
      .map((r) => r.dimensions[0]?.avg_hours_transcript_to_finalize as number | null)
      .filter((v): v is number => v !== null && v !== undefined)
    if (rows.length === 0) return null
    return rows.reduce((a, b) => a + b, 0) / rows.length
  }, [turnaround.data])

  const totalTokens = useMemo(() => {
    let tokens = 0
    for (const rollup of llmUsage.data?.rollups ?? []) {
      for (const dim of rollup.dimensions) {
        tokens += ((dim.tokens_input as number) ?? 0) + ((dim.tokens_output as number) ?? 0)
      }
    }
    return tokens
  }, [llmUsage.data])

  const isLoading = volume.isLoading || codingMix.isLoading || reimbursement.isLoading

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">Analytics</h1>
          <p className="mt-1 text-sm text-ink-500">Revenue, coding mix, and productivity across your organization.</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <Label htmlFor="start">From</Label>
            <Input id="start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="end">To</Label>
            <Input id="end" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          <Button variant="secondary" onClick={() => rollupMutation.mutate()} loading={rollupMutation.isPending}>
            <RefreshCw className="h-4 w-4" />
            Recompute
          </Button>
        </div>
      </div>

      {isLoading ? (
        <FullPageSpinner />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="Encounters"
              value={String(volumeChartData.reduce((a, b) => a + b.count, 0))}
              hint="In selected range"
              icon={<Users className="h-4 w-4" />}
              tone="brand"
            />
            <StatTile
              label="Estimated reimbursement"
              value={formatCurrency(totalReimbursement)}
              hint="Accepted codes x rate table"
              icon={<DollarSign className="h-4 w-4" />}
              tone="teal"
            />
            <StatTile
              label="Avg. turnaround"
              value={avgTurnaround !== null ? `${avgTurnaround.toFixed(1)}h` : "—"}
              hint="Transcript to finalized"
              icon={<Clock className="h-4 w-4" />}
              tone="amber"
            />
            <StatTile
              label="LLM tokens used"
              value={totalTokens.toLocaleString()}
              hint="Across all providers"
              icon={<Activity className="h-4 w-4" />}
              tone="rose"
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Encounter volume</CardTitle>
                <ExportButton rollupType="encounter_volume" startDate={startDate} endDate={endDate} />
              </CardHeader>
              <CardBody>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={volumeChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#eceef2" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#8891a3" />
                      <YAxis tick={{ fontSize: 12 }} stroke="#8891a3" allowDecimals={false} />
                      <Tooltip />
                      <Bar dataKey="count" fill="#2f57f5" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Coding mix</CardTitle>
                <ExportButton rollupType="coding_mix" startDate={startDate} endDate={endDate} />
              </CardHeader>
              <CardBody>
                {codingMixData.length > 0 ? (
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={codingMixData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85}>
                          {codingMixData.map((_, i) => (
                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                          ))}
                        </Pie>
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="py-16 text-center text-sm text-ink-400">No coded encounters in this range.</p>
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex items-center justify-between">
              <CardTitle>LLM usage and estimated cost</CardTitle>
              <ExportButton rollupType="llm_usage" startDate={startDate} endDate={endDate} />
            </CardHeader>
            <CardBody className="p-0">
              <LlmUsageTable rollups={llmUsage.data?.rollups ?? []} />
            </CardBody>
          </Card>
        </>
      )}
    </div>
  )
}

function ExportButton({ rollupType, startDate, endDate }: { rollupType: RollupType; startDate: string; endDate: string }) {
  return (
    <div className="flex gap-2">
      <button
        className="text-xs font-medium text-brand-600 hover:text-brand-700"
        onClick={() => downloadAnalyticsExport(rollupType, startDate, endDate, "csv")}
      >
        <Download className="mr-1 inline h-3 w-3" />
        CSV
      </button>
      <button
        className="text-xs font-medium text-brand-600 hover:text-brand-700"
        onClick={() => downloadAnalyticsExport(rollupType, startDate, endDate, "xlsx")}
      >
        <Download className="mr-1 inline h-3 w-3" />
        Excel
      </button>
    </div>
  )
}

interface LlmUsageRow {
  period: string
  provider: string
  calls: number
  tokens_input: number
  tokens_output: number
  estimated_cost_usd: number
}

function LlmUsageTable({ rollups }: { rollups: { period: string; dimensions: Record<string, unknown>[] }[] }) {
  const rows: LlmUsageRow[] = rollups.flatMap((r) =>
    r.dimensions.map((d) => ({ period: r.period, ...d }) as unknown as LlmUsageRow)
  )
  if (rows.length === 0) {
    return <p className="px-6 py-8 text-center text-sm text-ink-400">No LLM usage recorded in this range.</p>
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-ink-100 text-xs uppercase tracking-wide text-ink-400">
        <tr>
          <th className="px-6 py-3 font-medium">Date</th>
          <th className="px-6 py-3 font-medium">Provider</th>
          <th className="px-6 py-3 font-medium">Calls</th>
          <th className="px-6 py-3 font-medium">Tokens in</th>
          <th className="px-6 py-3 font-medium">Tokens out</th>
          <th className="px-6 py-3 font-medium">Est. cost</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-ink-100">
        {rows.map((row, i) => (
          <tr key={i}>
            <td className="px-6 py-3">{String(row.period)}</td>
            <td className="px-6 py-3 capitalize">{String(row.provider)}</td>
            <td className="px-6 py-3">{String(row.calls)}</td>
            <td className="px-6 py-3">{String(row.tokens_input)}</td>
            <td className="px-6 py-3">{String(row.tokens_output)}</td>
            <td className="px-6 py-3">{formatCurrency(Number(row.estimated_cost_usd ?? 0))}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
