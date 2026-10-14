"""Facilities: the shop space side - leases, rent, and the landlord."""

from backend.llm import make_agent
from backend.models import AgentReport

facilities = make_agent(
    "facilities",
    AgentReport,
    "Handles the shop space: leases, rent due dates, and landlord notices.",
)
