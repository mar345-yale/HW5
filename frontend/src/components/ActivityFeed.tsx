import { useEffect, useRef } from 'react'
import { AGENTS } from '../agents'
import { describe } from '../describe'
import type { Actor, AgentEvent } from '../types'

const time = (ts: string) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

/** Live, readable log of what every agent said and did on the selected ticket. */
export function ActivityFeed({ events }: { events: AgentEvent[] }) {
  const lines = events.flatMap(describe)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [lines.length])

  if (lines.length === 0) {
    return <p className="empty-note">No activity yet. Start the agent team to watch them work here.</p>
  }

  return (
    <div className="feed">
      {lines.map((l) => {
        const who = AGENTS[l.actor as Actor] ?? AGENTS.backend
        return (
          <div key={l.key} className={`feed-line ${l.tone}`}>
            <span className="feed-avatar" title={who.name}>{who.face}</span>
            <div className="feed-body">
              <div className="feed-meta">
                <strong>{who.name}</strong> <span className="muted small">{time(l.ts)}</span>
              </div>
              <div className="feed-text">{l.text}</div>
              {l.detail && (
                <details>
                  <summary>details</summary>
                  <pre>{l.detail}</pre>
                </details>
              )}
            </div>
          </div>
        )
      })}
      <div ref={end} />
    </div>
  )
}
