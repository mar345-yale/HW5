"""Customer Service: drafts messages to customers and requesters. Never sends them."""

from backend.llm import make_agent
from backend.models import AgentReport

customer_service = make_agent(
    "customer_service",
    AgentReport,
    "Drafts messages for customers and requesters; drafts stay on the board.",
)
