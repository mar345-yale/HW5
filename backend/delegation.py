"""The `delegate` tool: full connectivity between all five agents.

Any agent can hand a task to any other agent. The guards below keep that cheap:
no delegating to yourself, no loops back up the chain, a depth cap, and a
per-ticket delegation budget. The child run shares the parent's usage counter,
so one set of UsageLimits caps the whole ticket no matter how work is split.
"""

from __future__ import annotations

import json
from dataclasses import replace

from pydantic_ai import DeferredToolRequests, RunContext

from backend.audit import run_logged
from backend.llm import MAX_DELEGATION_DEPTH, MAX_DELEGATIONS_PER_TICKET, PAY_TOOLS
from backend.models import AgentName, AgentReport, DelegationRecord, PendingApproval, TeamDeps


def _refuse(deps: TeamDeps, to: AgentName, task: str, reason: str) -> str:
    deps.state.delegations.append(
        DelegationRecord(
            from_agent=deps.current,
            to_agent=to,
            task=task,
            depth=len(deps.chain),
            refused_reason=reason,
        )
    )
    return f"Delegation refused: {reason} Finish with what you already have."


def _brief(deps: TeamDeps, task: str) -> str:
    lines = [f"Delegated by: {deps.current}", f"Chain so far: {' -> '.join(deps.chain)}", f"Task: {task}"]
    if deps.state.ticket_context is not None:
        # Hand over the ticket context the team already fetched, so the
        # specialist does not spend a tool call re-reading it.
        lines.append("Ticket context (get_ticket_details output, already fetched):")
        lines.append(json.dumps(deps.state.ticket_context, separators=(",", ":")))
    return "\n".join(lines)


async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> AgentReport | str:
    """Ask another Campus Customs agent to do part of the work and return its report.

    Use only when the task is in the other agent's scope and you cannot finish
    it with your own tools. Write `task` as one or two specific sentences: what
    you need, and which ids, SKUs, or amounts it concerns.

    Args:
        to: The agent to ask: boss, inventory, accounting, facilities, or customer_service.
        task: The specific question or job for that agent.
    """
    deps = ctx.deps
    if to == deps.current:
        return _refuse(deps, to, task, "you cannot delegate to yourself.")
    if to in deps.chain:
        return _refuse(deps, to, task, f"{to} is already working on this request above you.")
    if len(deps.chain) > MAX_DELEGATION_DEPTH:
        return _refuse(deps, to, task, "the delegation chain is already at its maximum depth.")
    used = sum(1 for d in deps.state.delegations if d.refused_reason is None)
    if used >= MAX_DELEGATIONS_PER_TICKET:
        return _refuse(deps, to, task, "this ticket has used its delegation budget.")

    record = DelegationRecord(from_agent=deps.current, to_agent=to, task=task, depth=len(deps.chain))
    deps.state.delegations.append(record)

    child_deps = replace(deps, chain=[*deps.chain, to])
    result = await run_logged(
        deps.team[to],
        _brief(deps, task),
        ticket_run_id=deps.state.run_id,
        ticket_id=deps.state.ticket_id,
        chain=child_deps.chain,
        deps=child_deps,
        usage=ctx.usage,
        usage_limits=deps.usage_limits,
        output_type=[AgentReport, DeferredToolRequests],
    )
    if isinstance(result.output, DeferredToolRequests):
        return _queue_for_human(deps, to, record, result.output)
    record.output = result.output
    return result.output


def _queue_for_human(
    deps: TeamDeps, agent: AgentName, record: DelegationRecord, requests: DeferredToolRequests
) -> str:
    """Safeguard 2: a pay-tool call never runs inside an agent loop.

    The agent's call was paused by the approval-required toolset. It is parked
    here as a PendingApproval, and only backend.approvals can run it, with the
    human's name filled in as approved_by.
    """
    queued = []
    for call in requests.approvals:
        if call.tool_name not in PAY_TOOLS:
            continue
        args = {k: v for k, v in call.args_as_dict().items() if k not in ("approved_by", "account")}
        deps.state.pending_approvals.append(
            PendingApproval(
                id=call.tool_call_id,
                ticket_id=deps.state.ticket_id,
                requested_by=agent,
                tool=call.tool_name,
                args=args,
            )
        )
        record.pending_approvals.append(call.tool_call_id)
        queued.append(f"{call.tool_name}({json.dumps(args)})")
    if not queued:
        return f"{agent} stopped without a report."
    return (
        f"{agent} requested {', '.join(queued)}. Nothing has been paid: each request is queued "
        "for human approval. List it in approvals_needed and set status waiting_on_approval."
    )
