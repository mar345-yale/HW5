import { useCallback, useEffect, useMemo, useState } from 'react'
import { API_URL, api } from './api'
import { STATUS_LABEL } from './agents'
import { latestDecision, liveAgents, summarize } from './describe'
import { ActivityFeed } from './components/ActivityFeed'
import { AgentSummary } from './components/AgentSummary'
import { AgentTeam } from './components/AgentTeam'
import { ApprovalBar } from './components/ApprovalBar'
import { CashCard } from './components/CashCard'
import { TicketList } from './components/TicketList'
import type { AgentEvent, Approval, Cash, RunStatus, Ticket } from './types'

const FAST = 1500 // while agents are working
const SLOW = 5000 // otherwise

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [dateToday, setDateToday] = useState('')
  const [runs, setRuns] = useState<RunStatus[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  // ?ticket=101 opens the board on that ticket (handy for links and screenshots).
  const [selected, setSelected] = useState<number | null>(() => {
    const id = Number(new URLSearchParams(location.search).get('ticket'))
    return Number.isInteger(id) && id > 0 ? id : null
  })
  const [offline, setOffline] = useState(false)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error'; text: string } | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('approver') ?? '')

  const activeRun = runs.find((r) => r.status === 'running') ?? runs.find((r) => r.status === 'queued') ?? null

  const refresh = useCallback(async () => {
    try {
      const [t, r, e, a, c] = await Promise.all([api.tickets(), api.runs(), api.events(), api.approvals(), api.cash()])
      setTickets(t.tickets)
      setDateToday(t.date_today)
      setRuns(r)
      setEvents(e)
      setApprovals(a)
      setCash(c)
      setOffline(false)
      // First load: open the ticket the team touched most recently, else the first ticket.
      setSelected((s) => s ?? r[0]?.ticket_id ?? t.tickets[0]?.id ?? null)
    } catch {
      setOffline(true)
    }
  }, [])

  // Poll the backend: fast while a run is going so the agents update live.
  useEffect(() => {
    refresh()
    const id = setInterval(refresh, activeRun ? FAST : SLOW)
    return () => clearInterval(id)
  }, [refresh, activeRun?.run_id, activeRun?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Follow the ticket the team is working on.
  useEffect(() => {
    if (activeRun) setSelected(activeRun.ticket_id)
  }, [activeRun?.run_id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!notice) return
    const t = setTimeout(() => setNotice(null), 6000)
    return () => clearTimeout(t)
  }, [notice])

  const ticket = tickets.find((t) => t.id === selected) ?? null
  const ticketEvents = useMemo(() => events.filter((e) => e.ticket_id === selected), [events, selected])
  const ticketRuns = runs.filter((r) => r.ticket_id === selected)
  const latestRun = ticketRuns[0] ?? null // runs come newest first
  const runEvents = useMemo(
    () => (latestRun ? ticketEvents.filter((e) => e.ticket_run_id === latestRun.run_id) : ticketEvents),
    [ticketEvents, latestRun],
  )
  const running = !!activeRun && activeRun.ticket_id === selected && activeRun.status === 'running'
  const live = liveAgents(runEvents, running)
  const summaries = summarize(ticketEvents)
  const decision = latestDecision(ticketEvents)

  const startRun = async () => {
    if (selected == null) return
    try {
      await api.runTicket(selected)
      setNotice({ tone: 'ok', text: `Agent team started on ticket #${selected}.` })
      refresh()
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
  }

  const approve = async (a: Approval) => {
    try {
      const res = await api.approve(a.id, approver.trim())
      if (res.ok) {
        setNotice({
          tone: 'ok',
          text: `Paid. ${res.recheck_run ? `Boss is re-checking ticket #${a.ticket_id} to see if anything is left.` : ''}`,
        })
      } else {
        setNotice({ tone: 'error', text: `The pay tool refused: ${res.approval.result?.refused ?? 'unknown reason'}` })
      }
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
    refresh()
  }

  const deny = async (a: Approval) => {
    try {
      await api.deny(a.id, approver.trim())
      setNotice({ tone: 'ok', text: 'Denied. Nothing was paid.' })
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
    refresh()
  }

  const reset = async () => {
    if (!confirm('Reset the shop database to its original values? Payments, ticket updates, and drafts will be cleared.')) return
    try {
      await api.reset()
      setNotice({ tone: 'ok', text: 'Shop reset to the original data. Ready for a fresh run.' })
    } catch (err) {
      setNotice({ tone: 'error', text: (err as Error).message })
    }
    refresh()
  }

  const changeApprover = (name: string) => {
    setApprover(name)
    localStorage.setItem('approver', name)
  }

  return (
    <div className="page">
      <header className="top">
        <div className="brand">
          <span className="logo">🐶</span>
          <div>
            <h1>Campus Customs · Agent Desk</h1>
            <span className="muted">Shop date {dateToday || '—'} · watch the agent team work your tickets</span>
          </div>
        </div>
        <div className="top-right">
          <CashCard cash={cash} />
          <button className="ghost-btn" onClick={reset} disabled={!!activeRun}>
            ↺ Reset shop
          </button>
        </div>
      </header>

      {offline && (
        <div className="banner error">
          Can't reach the backend at {API_URL}. Start it from <code>backend/</code> with{' '}
          <code>uvicorn main:app --reload --port 8000</code>.
        </div>
      )}
      {notice && <div className={`banner ${notice.tone}`}>{notice.text}</div>}

      <ApprovalBar
        approvals={approvals}
        approver={approver}
        onApproverChange={changeApprover}
        onApprove={approve}
        onDeny={deny}
      />

      <main className="grid">
        <aside className="card">
          <TicketList tickets={tickets} selected={selected} activeRun={activeRun} onSelect={setSelected} />
        </aside>

        <section className="card work">
          {ticket ? (
            <>
              <div className="work-head">
                <div>
                  <span className="muted small">
                    Ticket #{ticket.id} · {ticket.requester}
                  </span>
                  <h2>{ticket.subject}</h2>
                  <span className="muted">{ticket.notes?.split('\n')[0]}</span>
                </div>
                <div className="work-actions">
                  <span className={`chip big ${running ? 'running' : ticket.status}`}>
                    {running ? 'Agents working' : STATUS_LABEL[ticket.status] ?? ticket.status}
                  </span>
                  <button className="primary-btn" onClick={startRun} disabled={!!activeRun}>
                    {activeRun
                      ? activeRun.ticket_id === ticket.id
                        ? 'Team is working…'
                        : `Team busy on #${activeRun.ticket_id}`
                      : ticketRuns.length
                        ? '▶ Run agent team again'
                        : '▶ Start agent team'}
                  </button>
                </div>
              </div>

              <h3 className="section-title">The team</h3>
              <AgentTeam live={live} />

              <div className="two-col">
                <div>
                  <h3 className="section-title">
                    Live activity{latestRun?.trigger === 'recheck' ? ' (re-check after approval)' : ''}
                  </h3>
                  <ActivityFeed events={runEvents} />
                </div>
                <div>
                  <h3 className="section-title">What each agent did</h3>
                  <AgentSummary summaries={summaries} decision={decision} />
                </div>
              </div>
            </>
          ) : (
            <p className="empty-note">Pick a ticket on the left.</p>
          )}
        </section>
      </main>
    </div>
  )
}
