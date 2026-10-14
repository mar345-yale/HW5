"""Append-only audit trail: output/audit_trail.json.

Every agent run goes through `run_logged`, which walks PydanticAI's agent loop
one node at a time and appends one record per step:

    user_prompt     an agent run starting (its chain and prompt size)
    model_request   the prompt, tool results, and retry prompts sent to the model
    model_response  the model's text and tool calls, model name, tokens used
    end             the agent's final output (a report, decision, or paused payment)
    error           anything that stopped the run (for example the usage cap)

The backend also appends its own events (payment approvals and denials, board
updates, resets) so money and data changes can be traced to a person.

The file is a JSON array that is only ever appended to. Each write adds one
record before the closing bracket, so earlier records are never rewritten and
the file stays valid JSON.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.agent import AgentRunResult
from pydantic_core import to_jsonable_python

AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit_trail.json"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def append(record: dict[str, Any]) -> None:
    """Add one record to the end of the JSON array without touching earlier records."""
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **record}
    line = json.dumps(to_jsonable_python(record, fallback=str), ensure_ascii=False)
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        AUDIT_PATH.write_text(f"[\n{line}\n]\n", encoding="utf-8")
        return
    with AUDIT_PATH.open("rb+") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        # Walk back past trailing whitespace to the closing bracket.
        while pos > 0:
            pos -= 1
            f.seek(pos)
            ch = f.read(1)
            if not ch.isspace():
                break
        if ch != b"]":
            raise ValueError(f"{AUDIT_PATH} is not a JSON array; refusing to append.")
        end = pos
        # An empty array ("[]") takes no leading comma.
        while pos > 0:
            pos -= 1
            f.seek(pos)
            prev = f.read(1)
            if not prev.isspace():
                break
        sep = "" if prev == b"[" else ","
        f.seek(end)
        f.write(f"{sep}\n{line}\n]\n".encode("utf-8"))
        f.truncate()


def _parts(parts: list[Any], kinds: set[str]) -> list[dict[str, Any]]:
    out = []
    for p in parts:
        kind = getattr(p, "part_kind", type(p).__name__)
        if kind not in kinds:
            continue
        item: dict[str, Any] = {"kind": kind}
        for attr in ("tool_name", "tool_call_id", "args", "content"):
            if hasattr(p, attr):
                item[attr] = getattr(p, attr)
        out.append(item)
    return out


def _step(node: Any) -> dict[str, Any]:
    name = type(node).__name__
    if name == "UserPromptNode":
        # The full prompt is logged once, in the model_request step that follows.
        return {"kind": "user_prompt", "prompt_chars": len(str(node.user_prompt or ""))}
    if name == "ModelRequestNode":
        return {
            "kind": "model_request",
            "parts": _parts(node.request.parts, {"user-prompt", "tool-return", "retry-prompt"}),
        }
    if name == "CallToolsNode":
        r = node.model_response
        return {
            "kind": "model_response",
            "model": r.model_name,
            "parts": _parts(r.parts, {"text", "tool-call"}),
            "tokens": {"input": r.usage.input_tokens, "output": r.usage.output_tokens},
        }
    if name == "End":
        return {"kind": "end", "output": node.data.output}
    return {"kind": name}


async def run_logged(
    agent: Agent[Any, Any],
    prompt: str,
    *,
    ticket_run_id: str,
    ticket_id: int | None,
    chain: list[str],
    **run_kwargs: Any,
) -> AgentRunResult[Any]:
    """`agent.run`, but every step of the loop is appended to the audit trail."""
    base = {
        "ticket_run_id": ticket_run_id,
        "ticket_id": ticket_id,
        "agent": chain[-1],
        "agent_run_id": new_id(),
        "chain": chain,
    }
    usage = run_kwargs.get("usage")
    step = 0
    try:
        async with agent.iter(prompt, **run_kwargs) as run:
            async for node in run:
                step += 1
                record = {**base, "step": step, **_step(node)}
                if usage is not None:
                    record["ticket_tokens_so_far"] = {
                        "requests": usage.requests,
                        "input": usage.input_tokens,
                        "output": usage.output_tokens,
                    }
                append(record)
        return run.result
    except Exception as exc:
        append({**base, "step": step + 1, "kind": "error", "error": f"{type(exc).__name__}: {exc}"})
        raise


# ---------------------------------------------------------------- reading the trail


def _clip(value: Any, n: int = 400) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[:n] + "…"


def _simplify(r: dict[str, Any]) -> dict[str, Any] | None:
    """One audit record -> one board event: who acted, what they said, which tools they used."""
    event = {k: r.get(k) for k in ("ts", "ticket_id", "ticket_run_id", "agent", "chain", "kind")}
    kind = r.get("kind")
    if kind == "user_prompt":
        return None  # the next model_request carries the same prompt
    if kind == "model_request":
        parts = r.get("parts", [])
        prompts = [p for p in parts if p["kind"] == "user-prompt"]
        if prompts:
            # Keep only the task line(s); the ticket context JSON is too big for the board.
            text = str(prompts[0].get("content", ""))
            event["task"] = _clip(text.split("Ticket context")[0].strip(), 300)
        event["tool_results"] = [
            {"tool": p.get("tool_name"), "result": _clip(p.get("content"))}
            for p in parts if p["kind"] in ("tool-return", "retry-prompt")
        ]
        if not prompts and not event["tool_results"]:
            return None
    elif kind == "model_response":
        parts = r.get("parts", [])
        event["said"] = " ".join(p["content"] for p in parts if p["kind"] == "text" and p.get("content")) or None
        event["tool_calls"] = [
            {"tool": p.get("tool_name"), "args": p.get("args")} for p in parts if p["kind"] == "tool-call"
        ]
        event["tokens"] = r.get("tokens")
    elif kind == "end":
        event["output"] = r.get("output")
    else:  # backend and human events: board_write, ticket_done, payment_decision, reset, error
        event.update({k: v for k, v in r.items() if k not in event})
    return event


def read_events(
    limit: int = 100,
    since: str | None = None,
    ticket_id: int | None = None,
    since_last_reset: bool = False,
) -> list[dict[str, Any]]:
    """The most recent board events, oldest first. `since` is an ISO timestamp from a previous event.

    With since_last_reset, records from before the most recent db reset are skipped,
    so the board only shows work done on the current copy of the shop.
    """
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    records = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if since_last_reset:
        resets = [i for i, r in enumerate(records) if r.get("kind") == "reset"]
        if resets:
            records = records[resets[-1] + 1:]
    events = []
    for r in records:
        if since and r.get("ts", "") <= since:
            continue
        if ticket_id is not None and r.get("ticket_id") != ticket_id:
            continue
        e = _simplify(r)
        if e is not None:
            events.append(e)
    return events[-limit:]
