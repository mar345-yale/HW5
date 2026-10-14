// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type Actor = AgentName | 'backend' | 'human'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string // open | waiting_on_approval | blocked | needs_info | resolved
  state: 'open' | 'resolved'
  notes: string | null
  created_at: string
}

export interface TicketsResponse {
  date_today: string
  tickets: Ticket[]
}

export interface ProposedAction {
  kind: string
  description: string
  amount: number | null
  ref_table: string | null
  ref_id: number | null
  requires_human_approval: boolean
}

export interface TicketDecision {
  ticket_id: number
  owner: AgentName
  status: string
  decision: string
  actions: ProposedAction[]
  customer_draft: string | null
  approvals_needed: string[]
}

export interface AgentReport {
  agent: AgentName
  summary: string
  recommendation: string
  proposed_actions: ProposedAction[]
  draft_message: string | null
  blockers: string[]
}

export interface RunStatus {
  run_id: string
  ticket_id: number
  trigger: 'user' | 'recheck'
  status: 'queued' | 'running' | 'done' | 'error'
  started_at: string
  finished_at: string | null
  error: string | null
  result: {
    decision: TicketDecision | null
    requests: number
    input_tokens: number
    output_tokens: number
  } | null
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown> | string | null
}

export interface AgentEvent {
  ts: string
  ticket_id: number | null
  ticket_run_id: string | null
  agent: Actor
  chain: AgentName[] | null
  kind: string // model_request | model_response | end | error | board_write | ticket_done | payment_decision | reset
  task?: string
  said?: string | null
  tool_calls?: ToolCall[]
  tool_results?: { tool: string; result: string }[]
  output?: unknown
  // backend / human events
  tool?: string
  args?: Record<string, unknown>
  status?: string
  decision?: string
  by?: string
  error?: string
  usage?: { requests: number; input: number; output: number }
}

export interface Approval {
  id: string
  ticket_id: number | null
  requested_by: AgentName
  tool: 'pay_invoice' | 'pay_rent'
  args: Record<string, unknown>
  status: 'pending' | 'approved' | 'denied'
  details: { title: string; amount: number; description: string } | null
}

export interface Cash {
  date_today: string
  account: string
  balance: number
  as_of: string
  total_due: number
  cash_after_paying_all: number
}
