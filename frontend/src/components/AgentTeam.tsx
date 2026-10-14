import { AGENTS, AGENT_ORDER } from '../agents'
import type { AgentLive } from '../describe'
import type { AgentName } from '../types'

const STATE_LABEL = { idle: 'Idle', working: 'Working', waiting: 'Waiting', done: 'Done' }

/** The five agents as emoji characters. The ones working right now glow. */
export function AgentTeam({ live }: { live: Record<AgentName, AgentLive> }) {
  return (
    <div className="team">
      {AGENT_ORDER.map((a) => {
        const meta = AGENTS[a]
        const { state, line } = live[a]
        return (
          <div key={a} className={`agent ${state}`}>
            <div className="avatar">
              <span className="face">{meta.face}</span>
              <span className="badge">{meta.badge}</span>
            </div>
            <div className="agent-name">{meta.name}</div>
            <div className={`agent-state ${state}`}>{STATE_LABEL[state]}</div>
            <div className="agent-line" title={line || meta.role}>
              {line || <span className="muted">{meta.role}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}
