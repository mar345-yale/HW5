"""Inventory: stock by SKU and size, shortfalls, and which vendor can restock."""

from backend.llm import make_agent
from backend.models import AgentReport

inventory = make_agent(
    "inventory",
    AgentReport,
    "Checks stock by SKU and size, spots shortfalls, and finds the vendor who can restock.",
)
