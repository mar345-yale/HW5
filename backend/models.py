"""Data types shared by the Campus Customs agent team.

Agent outputs are small, typed objects instead of free text. That keeps each
reply short (fewer output tokens), makes delegation results cheap to pass back
up the chain, and gives the dashboard fields it can render without parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.usage import UsageLimits

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

TicketStatus = Literal["resolved", "waiting_on_approval", "blocked", "needs_info"]

ActionKind = Literal[
    "pay_invoice",
    "pay_rent",
    "purchase_order",
    "restock_request",
    "price_decision",
    "customer_message",
    "update_ticket",
    "other",
]


# ---------------------------------------------------------------- agent outputs


class Fact(BaseModel):
    """One value an agent read from a tool. Every number must trace to a table."""

    label: str = Field(description="Short name, e.g. 'S tee on hand'.")
    value: str = Field(description="The value exactly as the tool returned it.")
    source: str = Field(description="table.column it came from, e.g. 'inventory.qty'.")


class ProposedAction(BaseModel):
    """Something the team wants done. Payments and POs always need a human."""

    kind: ActionKind
    description: str = Field(description="One sentence: what, for whom, and why.")
    amount: float | None = Field(default=None, description="Dollars, only if taken from the db.")
    ref_table: str | None = Field(default=None, description="e.g. 'invoices', 'leases'.")
    ref_id: int | None = Field(default=None, description="Row id in ref_table.")
    requires_human_approval: bool = True


class AgentReport(BaseModel):
    """What a specialist returns to whoever delegated to it."""

    agent: AgentName
    summary: str = Field(description="Two sentences max on what was found.")
    facts: list[Fact] = Field(default_factory=list)
    recommendation: str = Field(description="One or two sentences on what should happen next.")
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    draft_message: str | None = Field(
        default=None, description="Customer or landlord draft. Never sent; stays on the board."
    )
    blockers: list[str] = Field(default_factory=list, description="What stops progress right now.")


class TicketDecision(BaseModel):
    """Boss's final call on one ticket."""

    ticket_id: int
    owner: AgentName = Field(description="The agent primarily responsible for the ticket.")
    status: TicketStatus
    decision: str = Field(description="The final call in two or three sentences.")
    facts: list[Fact] = Field(default_factory=list)
    actions: list[ProposedAction] = Field(default_factory=list)
    customer_draft: str | None = None
    approvals_needed: list[str] = Field(
        default_factory=list, description="Each item a human must approve, one line each."
    )


# ---------------------------------------------------------------- run records


class PendingApproval(BaseModel):
    """A pay-tool call an agent made, paused until a human approves or denies it."""

    id: str = Field(description="The agent's tool_call_id, unique per request.")
    ticket_id: int | None
    requested_by: AgentName
    tool: Literal["pay_invoice", "pay_rent"]
    args: dict[str, Any] = Field(description="The agent's arguments, with any approved_by removed.")
    status: Literal["pending", "approved", "denied"] = "pending"
    approved_by: str | None = None
    result: dict[str, Any] | None = Field(default=None, description="The MCP tool's reply once run.")


class DelegationRecord(BaseModel):
    """One hop in the team graph, kept for the dashboard and for debugging cost."""

    from_agent: AgentName
    to_agent: AgentName
    task: str
    depth: int
    output: AgentReport | None = None
    pending_approvals: list[str] = Field(default_factory=list, description="PendingApproval ids.")
    refused_reason: str | None = None


class TicketRun(BaseModel):
    """Everything produced while working one ticket."""

    ticket_id: int
    decision: TicketDecision | None = None
    delegations: list[DelegationRecord] = Field(default_factory=list)
    pending_approvals: list[PendingApproval] = Field(default_factory=list)
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


# ---------------------------------------------------------------- run dependencies


@dataclass
class TicketState:
    """Mutable state shared by every agent working the same ticket."""

    ticket_id: int | None
    ticket_context: dict[str, Any] | None
    run_id: str = ""
    delegations: list[DelegationRecord] = field(default_factory=list)
    pending_approvals: list[PendingApproval] = field(default_factory=list)


@dataclass
class TeamDeps:
    """Passed to every agent run. `chain` is the path of agents from Boss down to this one."""

    team: dict[AgentName, "Agent[TeamDeps, Any]"]
    state: TicketState
    usage_limits: "UsageLimits"
    chain: list[AgentName] = field(default_factory=lambda: ["boss"])

    @property
    def current(self) -> AgentName:
        return self.chain[-1]
