import type { Actor, AgentName } from './types'

export interface AgentMeta {
  name: string
  face: string // the agent's "person"
  badge: string // the prop that tells you their job
  role: string
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export const AGENTS: Record<Actor, AgentMeta> = {
  boss: { name: 'Boss', face: '🤵', badge: '👔', role: 'Reads tickets, routes work, makes the final call' },
  inventory: { name: 'Inventory', face: '🧑‍🏭', badge: '📦', role: 'Stock, shortfalls, and restock vendors' },
  accounting: { name: 'Accounting', face: '🤓', badge: '🧮', role: 'Cash, invoices, and margins' },
  facilities: { name: 'Facilities', face: '👷', badge: '🏢', role: 'The lease, rent, and landlord' },
  customer_service: { name: 'Customer Service', face: '😊', badge: '🎧', role: 'Drafts replies to customers' },
  human: { name: 'You', face: '🙋', badge: '✅', role: 'Human approver' },
  backend: { name: 'Board', face: '🗂️', badge: '⚙️', role: 'Saves results to the shop database' },
}

export const STATUS_LABEL: Record<string, string> = {
  open: 'Open',
  waiting_on_approval: 'Waiting on approval',
  blocked: 'Blocked',
  needs_info: 'Needs info',
  resolved: 'Resolved',
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: n % 1 ? 2 : 0 })
