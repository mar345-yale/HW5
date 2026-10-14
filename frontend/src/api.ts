import type { Approval, AgentEvent, Cash, RunStatus, TicketsResponse } from './types'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new Error(body?.detail ?? `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  tickets: () => call<TicketsResponse>('/api/tickets'),
  runs: () => call<RunStatus[]>('/api/runs'),
  events: () => call<AgentEvent[]>('/api/events?limit=500'),
  approvals: () => call<Approval[]>('/api/approvals'),
  cash: () => call<Cash>('/api/cash'),
  runTicket: (id: number) => call<RunStatus>(`/api/tickets/${id}/run`, { method: 'POST' }),
  approve: (id: string, approvedBy: string) =>
    call<{ ok: boolean; approval: Approval & { result?: { refused?: string } }; recheck_run: RunStatus | null }>(
      `/api/approvals/${encodeURIComponent(id)}/approve`,
      { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) },
    ),
  deny: (id: string, deniedBy: string) =>
    call<{ ok: boolean }>(`/api/approvals/${encodeURIComponent(id)}/deny`, {
      method: 'POST',
      body: JSON.stringify({ denied_by: deniedBy }),
    }),
  reset: () => call<unknown>('/api/reset', { method: 'POST' }),
}
