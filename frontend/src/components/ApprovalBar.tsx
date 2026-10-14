import { useRef, useState } from 'react'
import { AGENTS, money } from '../agents'
import type { Approval } from '../types'

interface Props {
  approvals: Approval[]
  approver: string
  onApproverChange: (name: string) => void
  onApprove: (a: Approval) => Promise<void>
  onDeny: (a: Approval) => Promise<void>
}

/** Pinned to the top of the board: every payment an agent asked for, waiting on a human. */
export function ApprovalBar({ approvals, approver, onApproverChange, onApprove, onDeny }: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const [needName, setNeedName] = useState(false)
  const nameBox = useRef<HTMLInputElement>(null)

  if (approvals.length === 0) {
    return (
      <section className="approval-bar calm">
        <span className="calm-icon">✓</span>
        <div>
          <strong>No approvals needed right now.</strong>
          <span className="muted"> When an agent asks to pay a bill, it will appear here for you to approve.</span>
        </div>
      </section>
    )
  }

  const act = async (a: Approval, fn: (a: Approval) => Promise<void>) => {
    if (!approver.trim()) {
      setNeedName(true) // the pay tool needs a real person's name
      nameBox.current?.focus()
      return
    }
    setBusy(a.id)
    try {
      await fn(a)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="approval-bar alert">
      <div className="approval-head">
        <h2>Approval required</h2>
        <label className={`approver ${needName && !approver.trim() ? 'need' : ''}`}>
          {needName && !approver.trim() ? 'Type your name to approve →' : 'Approving as'}
          <input
            ref={nameBox}
            value={approver}
            placeholder="Your name"
            onChange={(e) => onApproverChange(e.target.value)}
            aria-label="Your name"
          />
        </label>
      </div>
      {approvals.map((a) => {
        const who = AGENTS[a.requested_by]
        const amount = a.details ? money(a.details.amount) : ''
        return (
          <div className="approval-row" key={a.id}>
            <button
              className="approve-btn"
              disabled={busy === a.id}
              onClick={() => act(a, onApprove)}
            >
              {busy === a.id ? 'Paying…' : `Approve ${amount}`}
            </button>
            <div className="approval-text">
              <strong>{a.details?.title ?? `${a.tool} ${JSON.stringify(a.args)}`}</strong>
              <span>
                {a.details?.description ?? 'This bill is no longer open; the pay tool will refuse it.'}
              </span>
              <span className="muted small">
                Ticket #{a.ticket_id} · requested by {who.face} {who.name} · cash moves only when you approve
              </span>
            </div>
            <button className="deny-btn" disabled={busy === a.id} onClick={() => act(a, onDeny)}>
              Deny
            </button>
          </div>
        )
      })}
    </section>
  )
}
