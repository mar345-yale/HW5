"""Accounting: cash, invoices, margins, and payments/POs prepped for human approval."""

from backend.llm import make_agent
from backend.models import AgentReport

accounting = make_agent(
    "accounting",
    AgentReport,
    "Watches cash and invoices, checks margins, and preps payments or POs for human approval.",
)
