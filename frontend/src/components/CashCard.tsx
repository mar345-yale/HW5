import { useEffect, useRef, useState } from 'react'
import { money } from '../agents'
import type { Cash } from '../types'

/** Checking balance. Pulses whenever the balance changes (e.g. after an approved payment). */
export function CashCard({ cash }: { cash: Cash | null }) {
  const last = useRef<number | null>(null)
  const [flash, setFlash] = useState(false)
  const balance = cash?.balance

  useEffect(() => {
    if (balance === undefined) return
    const prev = last.current
    last.current = balance
    if (prev !== null && prev !== balance) {
      setFlash(true)
      const t = setTimeout(() => setFlash(false), 1600)
      return () => clearTimeout(t)
    }
  }, [balance])

  return (
    <div className={`cash-card ${flash ? 'flash' : ''}`}>
      <span className="cash-label">Checking balance</span>
      <span className="cash-value">{cash ? money(cash.balance) : '—'}</span>
      {cash && (
        <span className="cash-sub">
          Bills due {money(cash.total_due)} · {money(cash.cash_after_paying_all)} left if all paid
        </span>
      )}
    </div>
  )
}
