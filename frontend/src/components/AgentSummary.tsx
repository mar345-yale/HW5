import { AGENTS, STATUS_LABEL } from '../agents'
import type { AgentSummary as Summary } from '../describe'
import type { TicketDecision } from '../types'

/** Short recap of each agent's part in the ticket, plus Boss's final call. */
export function AgentSummary({ summaries, decision }: { summaries: Summary[]; decision: TicketDecision | null }) {
  if (summaries.length === 0) {
    return <p className="empty-note">When a run finishes, each agent's part shows up here.</p>
  }
  return (
    <div className="summary">
      {decision && (
        <div className={`decision ${decision.status}`}>
          <div className="decision-top">
            <span className="decision-label">Boss's call</span>
            <span className={`chip ${decision.status}`}>{STATUS_LABEL[decision.status] ?? decision.status}</span>
          </div>
          <p>{decision.decision}</p>
          {decision.customer_draft && (
            <details>
              <summary>Customer draft (saved on the board, not sent)</summary>
              <p className="draft">{decision.customer_draft}</p>
            </details>
          )}
        </div>
      )}
      {summaries.map((s) => {
        const meta = AGENTS[s.agent]
        return (
          <div key={s.agent} className="summary-row">
            <span className="summary-avatar">{meta.face}</span>
            <div>
              <strong>{meta.name}</strong>
              <p>{s.summary || <span className="muted">Still working…</span>}</p>
              {s.tools.length > 0 && (
                <div className="tools">
                  {s.tools.map((t) => (
                    <span key={t} className="tool-pill">{t}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
