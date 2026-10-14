"""The human approval gate: the only code that can run a pay tool.

Agents can ask for a payment, but their call is paused (backend.llm) and
parked as a PendingApproval (backend.delegation). A human approves or denies
it here. On approval, the pay tool runs through the MCP server with the human's
name as approved_by. The MCP tool then applies its own checks (safeguard 1): a
real approver, an open bill, and enough cash.
"""

from __future__ import annotations

import json
from typing import Any

from backend.audit import append as audit
from backend.llm import MCP_TOOLS
from backend.models import PendingApproval


async def _mcp(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    async with MCP_TOOLS:
        result = await MCP_TOOLS.direct_call_tool(tool, args)
    return result if isinstance(result, dict) else json.loads(result)


def _audit(p: PendingApproval, decision: str, by: str, reason: str = "") -> None:
    audit({
        "ticket_id": p.ticket_id, "agent": "human", "kind": "payment_decision", "approval_id": p.id,
        "requested_by": p.requested_by, "tool": p.tool, "args": p.args, "decision": decision,
        "by": by, "reason": reason or None, "result": p.result,
    })


def describe(p: PendingApproval) -> str:
    target = ", ".join(f"{k}={v}" for k, v in p.args.items())
    return f"[ticket {p.ticket_id}] {p.requested_by} asks to {p.tool}({target})"


async def approve(p: PendingApproval, approved_by: str) -> PendingApproval:
    """Run the paused pay tool with a human approver.

    The MCP tool may still refuse (not a human approver, bill not open, not
    enough cash). A refused request stays pending so a human can retry or deny it.
    """
    if p.status != "pending":
        raise ValueError(f"Approval {p.id} is already {p.status}.")
    p.result = await _mcp(p.tool, {**p.args, "approved_by": approved_by})
    if not p.result.get("ok"):
        _audit(p, "approval_refused", approved_by)
        return p
    p.status = "approved"
    p.approved_by = approved_by
    _audit(p, "approved", approved_by)
    if p.ticket_id is not None:
        outcome = "paid" if p.result.get("ok") else f"refused by the pay tool: {p.result.get('refused')}"
        note = f"{p.tool}({json.dumps(p.args)}) approved by {approved_by}; {outcome}"
        await _mcp("update_ticket", {"ticket_id": p.ticket_id, "note": note, "author": "approvals"})
    return p


async def deny(p: PendingApproval, denied_by: str, reason: str = "") -> PendingApproval:
    """Record a denial on the ticket. Nothing is paid."""
    if p.status != "pending":
        raise ValueError(f"Approval {p.id} is already {p.status}.")
    p.status = "denied"
    p.approved_by = None
    _audit(p, "denied", denied_by, reason)
    if p.ticket_id is not None:
        note = f"{p.tool}({json.dumps(p.args)}) denied by {denied_by}" + (f": {reason}" if reason else "")
        await _mcp("update_ticket", {"ticket_id": p.ticket_id, "note": note, "author": "approvals"})
    return p


async def review_in_terminal(pending: list[PendingApproval]) -> None:
    """Ask a human at the terminal about each pending payment."""
    for p in pending:
        if p.status != "pending":
            continue
        print(f"\nPAYMENT REQUEST {describe(p)}")
        answer = input("  Type your name to APPROVE, 'n' to deny, or Enter to leave it pending: ").strip()
        if answer.lower() == "n":
            await deny(p, "terminal user")
            print("  Denied. Nothing was paid.")
        elif answer:
            await approve(p, answer)
            print(f"  Pay tool replied: {json.dumps(p.result)}")
        else:
            print("  Left pending.")
