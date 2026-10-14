"""Shared model, MCP connection, prompt loading, and cost limits.

Every agent uses one Portkey-routed gpt-6-luna model and one connection to the
campus-customs MCP server. The cost controls live here so they are easy to tune
in one place.
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import AbstractToolset, Agent, RunContext, ToolDefinition
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from backend.models import AgentName, TeamDeps

HW_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MCP_SERVER = HW_DIR / "mcp_server" / "server.py"

# PORTKEY_API_KEY comes from a .env next to backend/ (copy .env.example), or,
# inside the course repo, from the root AI Foundations/.env. Never commit a real .env.
for _env in (HW_DIR / ".env", HW_DIR.parents[1] / ".env"):
    if _env.exists():
        load_dotenv(_env)
        break
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# ---- cost controls ----------------------------------------------------------
# Boss -> specialist -> specialist is the deepest chain allowed.
MAX_DELEGATION_DEPTH = 2
# Total delegations across the whole team for one ticket.
MAX_DELEGATIONS_PER_TICKET = 4
# Hard ceiling for one ticket across every agent run it triggers.
TICKET_USAGE_LIMITS = UsageLimits(request_limit=16, total_tokens_limit=60_000)
# Specialists answer in a short structured report; Boss writes the final call.
SPECIALIST_MAX_TOKENS = 1_200
BOSS_MAX_TOKENS = 1_800


def _settings(name: AgentName, max_tokens: int) -> OpenAIResponsesModelSettings:
    return OpenAIResponsesModelSettings(
        max_tokens=max_tokens,
        openai_reasoning_effort="low",
        parallel_tool_calls=True,
        # A stable key per agent lets the static prompt + tool list be cached across runs.
        openai_prompt_cache_key=f"campus-customs-{name}",
    )


def _build_model() -> OpenAIResponsesModel:
    key = os.environ.get("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing: copy .env.example to .env and add your key")
    client = AsyncOpenAI(
        api_key=key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


MODEL = _build_model()

# One stdio connection to mcp_server/server.py, shared by all five agents.
MCP_TOOLS = MCPToolset(MCP_SERVER)

# ---- tool access ------------------------------------------------------------
# Each agent sees only its own MCP tools (smaller prompts, no wrong-agent calls).
# reset_shop_db, save_draft, update_ticket, and get_board_summary are called by
# the backend through this same MCP connection, never by an agent.
_SHARED_TOOLS = {"list_open_tickets", "get_ticket_details", "list_bills_due"}
AGENT_TOOLS: dict[AgentName, set[str]] = {
    "boss": _SHARED_TOOLS,
    "inventory": _SHARED_TOOLS | {"check_stock", "find_restock_vendors", "get_vendor_status"},
    "accounting": _SHARED_TOOLS | {"pay_invoice", "check_margin", "list_payments", "get_vendor_status"},
    "facilities": _SHARED_TOOLS | {"pay_rent", "get_lease"},
    "customer_service": _SHARED_TOOLS,
}
PAY_TOOLS = {"pay_invoice", "pay_rent"}
_HUMAN_ONLY_ARGS = {"approved_by", "account"}


def _hide_human_only_args(ctx: RunContext[TeamDeps], defs: list[ToolDefinition]) -> list[ToolDefinition]:
    """Remove approved_by/account from the pay tools' schemas so an agent cannot fill them."""
    out = []
    for d in defs:
        if d.name in PAY_TOOLS:
            schema = dict(d.parameters_json_schema)
            schema["properties"] = {
                k: v for k, v in schema.get("properties", {}).items() if k not in _HUMAN_ONLY_ARGS
            }
            schema["required"] = [r for r in schema.get("required", []) if r not in _HUMAN_ONLY_ARGS]
            d = replace(d, parameters_json_schema=schema)
        out.append(d)
    return out


def agent_toolset(name: AgentName) -> AbstractToolset[TeamDeps]:
    """This agent's slice of the MCP server. Pay tools always pause for a human (safeguard 2)."""
    allowed = AGENT_TOOLS[name]
    return (
        MCP_TOOLS.filtered(lambda ctx, td: td.name in allowed)
        .prepared(_hide_human_only_args)
        .approval_required(lambda ctx, td, args: td.name in PAY_TOOLS)
    )


def load_prompt(name: AgentName) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def make_agent(name: AgentName, output_type: Any, description: str) -> Agent[TeamDeps, Any]:
    """Build one team member: its prompt, the shared model, MCP tools, and `delegate`."""
    from backend.delegation import delegate

    max_tokens = BOSS_MAX_TOKENS if name == "boss" else SPECIALIST_MAX_TOKENS
    return Agent(
        MODEL,
        name=name,
        description=description,
        instructions=load_prompt(name),
        output_type=output_type,
        deps_type=TeamDeps,
        tools=[delegate],
        toolsets=[agent_toolset(name)],
        model_settings=_settings(name, max_tokens),
        retries=1,
    )
