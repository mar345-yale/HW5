import { STATUS_LABEL } from '../agents'
import type { RunStatus, Ticket } from '../types'

const TYPE_ICON: Record<string, string> = { customer_order: '👕', rent_notice: '🏠', price_override: '🏷️' }

interface Props {
  tickets: Ticket[]
  selected: number | null
  activeRun: RunStatus | null
  onSelect: (id: number) => void
}

export function TicketList({ tickets, selected, activeRun, onSelect }: Props) {
  return (
    <div className="ticket-list">
      <h2 className="section-title">Tickets</h2>
      {tickets.map((t) => {
        const running = activeRun?.ticket_id === t.id
        const status = running ? (activeRun?.status === 'queued' ? 'queued' : 'running') : t.status
        return (
          <button
            key={t.id}
            className={`ticket ${selected === t.id ? 'selected' : ''} ${t.state}`}
            onClick={() => onSelect(t.id)}
          >
            <span className="ticket-icon">{TYPE_ICON[t.type] ?? '📝'}</span>
            <span className="ticket-body">
              <span className="ticket-top">
                <span className="ticket-id">#{t.id}</span>
                <span className={`chip ${status}`}>
                  {running && <span className="dot" />}
                  {status === 'running' ? 'Agents working' : status === 'queued' ? 'Re-check queued' : STATUS_LABEL[status] ?? status}
                </span>
              </span>
              <span className="ticket-subject">{t.subject}</span>
              <span className="ticket-req">{t.requester}</span>
            </span>
          </button>
        )
      })}
    </div>
  )
}
