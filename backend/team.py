"""The team loop: wire the five agents together and work tickets through Boss.

For each ticket, the loop fetches the ticket's linked rows once over MCP (no
model call), hands them to Boss, and lets Boss delegate. When Boss decides, the
loop writes the decision back over MCP (update_ticket, save_draft), which costs
no tokens. Tickets run one at a time so a single ticket's usage cap holds.

Payments requested by agents come back as pending approvals. Nothing is paid
until a human approves them (backend.approvals).

    python -m backend.team --reset    # reset the db, then work every open ticket
    python -m backend.team 101 103    # just these tickets
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from pydantic_ai import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from backend.agents.accounting import accounting
from backend.agents.boss import boss
from backend.agents.customer_service import customer_service
from backend.agents.facilities import facilities
from backend.agents.inventory import inventory
from backend.approvals import review_in_terminal
from backend.audit import append as audit, new_id, run_logged
from backend.llm import MCP_TOOLS, TICKET_USAGE_LIMITS
from backend.models import AgentName, TeamDeps, TicketDecision, TicketRun, TicketState

TEAM: dict[AgentName, Any] = {
    "boss": boss,
    "inventory": inventory,
    "accounting": accounting,
    "facilities": facilities,
    "customer_service": customer_service,
}


async def _call(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await MCP_TOOLS.direct_call_tool(tool, args or {})
    return result if isinstance(result, dict) else json.loads(result)


async def run_ticket(ticket_id: int, run_id: str | None = None) -> TicketRun:
    """Work one ticket end to end. Call inside `async with MCP_TOOLS:`.

    `run_id` becomes the audit trail's ticket_run_id (the API passes its own id so they match).
    """
    context = await _call("get_ticket_details", {"ticket_id": ticket_id})
    state = TicketState(ticket_id=ticket_id, ticket_context=context, run_id=run_id or new_id())
    deps = TeamDeps(team=TEAM, state=state, usage_limits=TICKET_USAGE_LIMITS)
    usage = RunUsage()
    run = TicketRun(ticket_id=ticket_id)

    prompt = (
        f"Work ticket {ticket_id} and return your final decision.\n"
        "Ticket context (get_ticket_details output, already fetched):\n"
        + json.dumps(context, separators=(",", ":"))
    )
    try:
        result = await run_logged(
            boss,
            prompt,
            ticket_run_id=state.run_id,
            ticket_id=ticket_id,
            chain=deps.chain,
            deps=deps,
            usage=usage,
            usage_limits=TICKET_USAGE_LIMITS,
        )
        run.decision = result.output
        run.decision.ticket_id = ticket_id
    except UsageLimitExceeded as exc:
        run.error = f"Stopped at the usage cap: {exc}"

    if run.decision is not None:
        await _record_decision(run.decision, state.run_id)

    run.delegations = state.delegations
    run.pending_approvals = state.pending_approvals
    run.requests = usage.requests
    run.input_tokens = usage.input_tokens
    run.output_tokens = usage.output_tokens
    audit({
        "ticket_run_id": state.run_id, "ticket_id": ticket_id, "agent": "backend", "kind": "ticket_done",
        "status": run.decision.status if run.decision else None, "error": run.error,
        "delegations": len(state.delegations), "pending_approvals": [p.id for p in state.pending_approvals],
        "usage": {"requests": usage.requests, "input": usage.input_tokens, "output": usage.output_tokens},
    })
    return run


async def _record_decision(d: TicketDecision, run_id: str) -> None:
    """Put Boss's call on the board: ticket status + note, and the customer draft."""
    writes = [("update_ticket", {"ticket_id": d.ticket_id, "status": d.status, "note": d.decision})]
    if d.customer_draft:
        writes.append(("save_draft", {"ticket_id": d.ticket_id, "audience": "customer", "body": d.customer_draft}))
    for tool, args in writes:
        result = await _call(tool, args)
        audit({"ticket_run_id": run_id, "ticket_id": d.ticket_id, "agent": "backend",
               "kind": "board_write", "tool": tool, "args": args, "result": result})


async def reset_db() -> dict[str, Any]:
    async with MCP_TOOLS:
        result = await _call("reset_shop_db", {"confirm": True})
    audit({"agent": "backend", "kind": "reset", "tool": "reset_shop_db", "result": result})
    return result


async def run_board(ticket_ids: list[int] | None = None, run_id: str | None = None) -> list[TicketRun]:
    """Work the given tickets, or every open ticket on the board. `run_id` is only used for a single ticket."""
    async with MCP_TOOLS:
        if not ticket_ids:
            board = await _call("list_open_tickets")
            ticket_ids = [t["id"] for t in board["tickets"]]
        if run_id and len(ticket_ids) == 1:
            return [await run_ticket(ticket_ids[0], run_id)]
        return [await run_ticket(tid) for tid in ticket_ids]


async def _main(args: list[str]) -> None:
    if "--reset" in args:
        print("Reset:", json.dumps(await reset_db()))
    ids = [int(a) for a in args if a.isdigit()]
    runs = await run_board(ids or None)
    for run in runs:
        print(run.model_dump_json(indent=2, exclude_none=True))
    pending = [p for run in runs for p in run.pending_approvals]
    if pending and sys.stdin.isatty():
        await review_in_terminal(pending)
    elif pending:
        print(f"{len(pending)} payment request(s) left pending; no terminal to approve them.")


def main() -> None:
    asyncio.run(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
