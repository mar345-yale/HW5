// Turn raw audit-trail events into things a person can read on the board.
import { AGENTS, STATUS_LABEL } from './agents'
import type { AgentEvent, AgentName, AgentReport, TicketDecision, ToolCall } from './types'

export const AGENT_NAMES = new Set<string>(['boss', 'inventory', 'accounting', 'facilities', 'customer_service'])
const isAgent = (a: string): a is AgentName => AGENT_NAMES.has(a)

const name = (a: string) => AGENTS[a as AgentName]?.name ?? a

const HIDDEN_TOOLS = new Set(['final_result'])

/** Tool args arrive either as an object or as the model's raw JSON string. */
export function argsOf(args: ToolCall['args'] | undefined): Record<string, unknown> {
  if (!args) return {}
  if (typeof args === 'string') {
    try {
      const parsed = JSON.parse(args)
      return parsed && typeof parsed === 'object' ? parsed : {}
    } catch {
      return {}
    }
  }
  return args
}

function argsText(args: ToolCall['args'] | Record<string, unknown>): string {
  return Object.entries(argsOf(args as ToolCall['args']))
    .map(([k, v]) => `${k} ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

/** The "Task:" line of a delegation brief, or the first line of Boss's prompt. */
function taskText(task: string): string {
  const m = task.match(/Task:\s*([\s\S]*)/)
  return (m ? m[1] : task.split('\n')[0]).trim()
}

function isDeferred(output: unknown): output is { approvals: { tool_name: string; args: Record<string, unknown> }[] } {
  return !!output && typeof output === 'object' && 'approvals' in output
}
function isDecision(output: unknown): output is TicketDecision {
  return !!output && typeof output === 'object' && 'decision' in output && 'owner' in output
}
function isReport(output: unknown): output is AgentReport {
  return !!output && typeof output === 'object' && 'summary' in output && 'agent' in output
}

export interface FeedLine {
  key: string
  ts: string
  actor: string
  text: string
  detail?: string
  tone: 'normal' | 'tool' | 'result' | 'decision' | 'alert' | 'quiet'
}

/** One event can produce several readable lines (e.g. a response with two tool calls). */
export function describe(e: AgentEvent): FeedLine[] {
  const base = { ts: e.ts, actor: e.agent }
  const out: FeedLine[] = []
  const add = (text: string, tone: FeedLine['tone'], detail?: string) =>
    out.push({ ...base, key: `${e.ts}-${e.agent}-${out.length}`, text, tone, detail })

  switch (e.kind) {
    case 'model_request':
      if (e.task) {
        if (e.agent === 'boss' && !e.task.includes('Delegated by')) add(`Picked up ticket #${e.ticket_id}`, 'normal')
        else add(`Got a task: ${taskText(e.task)}`, 'normal')
      }
      for (const r of e.tool_results ?? []) {
        if (r.tool === 'delegate' || HIDDEN_TOOLS.has(r.tool)) continue
        add(`Read the result of ${r.tool}`, 'result', r.result)
      }
      break
    case 'model_response':
      if (e.said) add(`“${e.said}”`, 'normal')
      for (const c of e.tool_calls ?? []) {
        if (HIDDEN_TOOLS.has(c.tool)) continue
        const a = argsOf(c.args)
        if (c.tool === 'delegate') add(`Asked ${name(String(a.to))}: ${a.task ?? ''}`, 'tool')
        else if (c.tool.startsWith('pay_')) add(`Requested ${c.tool}(${argsText(c.args)}): needs your approval`, 'alert')
        else add(`Used ${c.tool}${argsText(c.args) ? ` (${argsText(c.args)})` : ''}`, 'tool')
      }
      break
    case 'end':
      if (isDecision(e.output)) {
        add(`Decided: ${STATUS_LABEL[e.output.status] ?? e.output.status}. ${e.output.decision}`, 'decision')
      } else if (isReport(e.output)) {
        add(`Reported back: ${e.output.summary}`, 'decision', e.output.recommendation)
      } else if (isDeferred(e.output)) {
        const reqs = e.output.approvals.map((x) => `${x.tool_name}(${argsText(x.args)})`).join(', ')
        add(`Paused: ${reqs} is waiting for a human to approve`, 'alert')
      }
      break
    case 'board_write':
      if (e.tool === 'update_ticket') add(`Ticket marked ${STATUS_LABEL[String(e.args?.status)] ?? e.args?.status}`, 'quiet')
      if (e.tool === 'save_draft') add('Saved the customer draft to the board (not sent)', 'quiet', String(e.args?.body ?? ''))
      break
    case 'ticket_done':
      add(
        `Run finished: ${e.usage?.requests ?? 0} model calls, ${((e.usage?.input ?? 0) + (e.usage?.output ?? 0)).toLocaleString()} tokens`,
        'quiet',
      )
      break
    case 'payment_decision':
      if (e.decision === 'approved') add(`${e.by} approved ${e.tool}: cash moved`, 'decision')
      else if (e.decision === 'denied') add(`${e.by} denied ${e.tool}: nothing paid`, 'quiet')
      else add(`The pay tool refused ${e.tool} (approver: ${e.by})`, 'alert')
      break
    case 'error':
      add(`Stopped: ${e.error}`, 'alert')
      break
  }
  return out
}

// ---------------------------------------------------------------- live agent state

export type AgentState = 'idle' | 'working' | 'waiting' | 'done'

export interface AgentLive {
  state: AgentState
  line: string // what they're saying/doing right now
}

/** Who is working, who is waiting on a teammate, and the latest thing each one did, for one run. */
export function liveAgents(runEvents: AgentEvent[], running: boolean): Record<AgentName, AgentLive> {
  const live = Object.fromEntries(
    [...AGENT_NAMES].map((a) => [a, { state: 'idle', line: '' } as AgentLive]),
  ) as Record<AgentName, AgentLive>
  const open = new Map<AgentName, AgentName[]>() // agent -> its chain while in progress

  for (const e of runEvents) {
    if (!isAgent(e.agent)) continue
    const lines = describe(e)
    if (lines.length) live[e.agent].line = lines[lines.length - 1].text
    if (e.kind === 'model_request' && e.task) {
      open.set(e.agent, e.chain ?? [e.agent])
      live[e.agent].state = 'working'
    }
    if (e.kind === 'end' || e.kind === 'error') {
      open.delete(e.agent)
      live[e.agent].state = 'done'
    }
  }
  if (!running) {
    for (const agent of open.keys()) live[agent].state = 'done'
  } else {
    for (const [agent, chain] of open) {
      // waiting = a teammate further down this agent's chain is still working
      const waitingOn = [...open.entries()].find(([other, c]) => other !== agent && c.length > chain.length && c.includes(agent))
      live[agent].state = waitingOn ? 'waiting' : 'working'
      if (waitingOn) live[agent].line = `Waiting on ${name(waitingOn[0])}…`
    }
  }
  return live
}

// ---------------------------------------------------------------- per-ticket summary

export interface AgentSummary {
  agent: AgentName
  tools: string[]
  summary: string
}

/** What each agent did on a ticket across all its runs since the last reset. */
export function summarize(ticketEvents: AgentEvent[]): AgentSummary[] {
  const byAgent = new Map<AgentName, AgentSummary>()
  const get = (a: AgentName) => {
    if (!byAgent.has(a)) byAgent.set(a, { agent: a, tools: [], summary: '' })
    return byAgent.get(a)!
  }
  for (const e of ticketEvents) {
    if (!isAgent(e.agent)) continue
    const s = get(e.agent)
    for (const c of e.tool_calls ?? []) {
      const label = c.tool === 'delegate' ? `delegate → ${name(String(argsOf(c.args).to))}` : c.tool
      if (!HIDDEN_TOOLS.has(c.tool) && !s.tools.includes(label)) s.tools.push(label)
    }
    if (e.kind === 'end') {
      if (isDecision(e.output)) s.summary = `${STATUS_LABEL[e.output.status] ?? e.output.status}: ${e.output.decision}`
      else if (isReport(e.output)) s.summary = e.output.summary
      else if (isDeferred(e.output))
        s.summary = `Requested ${e.output.approvals.map((x) => x.tool_name).join(', ')} and paused for human approval.`
    }
  }
  return [...byAgent.values()]
}

/** Boss's latest decision on a ticket, if any. */
export function latestDecision(ticketEvents: AgentEvent[]): TicketDecision | null {
  for (let i = ticketEvents.length - 1; i >= 0; i--) {
    const e = ticketEvents[i]
    if (e.agent === 'boss' && e.kind === 'end' && isDecision(e.output)) return e.output
  }
  return null
}

