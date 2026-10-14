"""Boss: reads each ticket, routes work to specialists, and makes the final call."""

from backend.llm import make_agent
from backend.models import TicketDecision

boss = make_agent(
    "boss",
    TicketDecision,
    "Reads each ticket, decides who works on it, and makes the final call.",
)
