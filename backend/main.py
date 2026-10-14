"""Campus Customs backend API for the React dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop fact and every change goes through the campus-customs MCP server
(the same connection the agents use). This file adds no shop logic of its own.

Routes (all JSON):
    GET  /api/tickets                    every ticket and whether it is open or resolved
    POST /api/tickets/{id}/run           start the agent team on one ticket (runs in the background)
    GET  /api/runs, /api/runs/{run_id}   run status and result
    GET  /api/events                     recent agent events from output/audit_trail.json
    GET  /api/approvals                  payment requests waiting for a human
    POST /api/approvals/{id}/approve     a human approves: the pay tool runs and cash changes;
                                         after a ticket's last approval, Boss re-checks that ticket
    POST /api/approvals/{id}/deny        a human denies: nothing is paid
    GET  /api/cash                       current checking balance from cash_accounts
    POST /api/reset                      reset the working db to the original values
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Running from backend/ puts backend/ itself on sys.path; the code imports the
# `backend` package, so add its parent (the Homework-5 folder) too.
HW_DIR = Path(__file__).resolve().parents[1]
if str(HW_DIR) not in sys.path:
    sys.path.insert(0, str(HW_DIR))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.approvals import approve, deny  # noqa: E402
from backend.audit import new_id, read_events  # noqa: E402
from backend.llm import MCP_TOOLS  # noqa: E402
from backend.models import PendingApproval, TicketRun  # noqa: E402
from backend.team import reset_db, run_board  # noqa: E402

# Pending payment requests survive a --reload restart. Kept in output/ so that
# writing it does not trigger the reloader, which only watches backend/.
PENDING_PATH = HW_DIR / "output" / "pending_approvals.json"


# ---------------------------------------------------------------- state


class RunStatus(BaseModel):
    run_id: str
    ticket_id: int
    trigger: str = "user"  # user | recheck (started automatically after a ticket's last approval)
    status: str  # queued | running | done | error
    started_at: str
    finished_at: str | None = None
    result: TicketRun | None = None
    error: str | None = None


RUNS: dict[str, RunStatus] = {}
ACTIVE_RUN: str | None = None  # one ticket at a time keeps the usage cap and the db consistent
PENDING: dict[str, PendingApproval] = {}
QUEUE: list[RunStatus] = []  # re-checks waiting for the active run to finish


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_pending() -> None:
    PENDING.clear()
    if PENDING_PATH.exists():
        for item in json.loads(PENDING_PATH.read_text(encoding="utf-8") or "[]"):
            p = PendingApproval.model_validate(item)
            PENDING[p.id] = p


def _save_pending() -> None:
    PENDING_PATH.write_text(
        json.dumps([p.model_dump() for p in PENDING.values()], indent=2), encoding="utf-8"
    )


async def _mcp(tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    result = await MCP_TOOLS.direct_call_tool(tool, args or {})
    return result if isinstance(result, dict) else json.loads(result)


# ---------------------------------------------------------------- app


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_pending()
    async with MCP_TOOLS:  # one MCP connection for the life of the server
        yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # the Vite dashboard
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # any other local dev port
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "active_run": ACTIVE_RUN}


# ---------------------------------------------------------------- tickets


@app.get("/api/tickets")
async def tickets() -> dict[str, Any]:
    """Every ticket with its raw status and a simple open/resolved state for the board."""
    board = await _mcp("list_tickets")
    for t in board["tickets"]:
        t["state"] = "resolved" if t["status"] == "resolved" else "open"
    return board


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> RunStatus:
    """Start the agent team on one ticket. Poll /api/runs/{run_id} and /api/events while it works."""
    if ACTIVE_RUN is not None:
        raise HTTPException(409, f"Run {ACTIVE_RUN} is still working; wait for it to finish.")
    details = await _mcp("get_ticket_details", {"ticket_id": ticket_id})
    if "error" in details:
        raise HTTPException(404, details["error"])
    if ACTIVE_RUN is not None:  # another click won the race while we were reading the ticket
        raise HTTPException(409, f"Run {ACTIVE_RUN} is still working; wait for it to finish.")
    return _start(RunStatus(run_id=new_id(), ticket_id=ticket_id, status="running", started_at=_now()))


def _start(run: RunStatus) -> RunStatus:
    global ACTIVE_RUN
    run.status = "running"
    RUNS[run.run_id] = run
    ACTIVE_RUN = run.run_id
    asyncio.create_task(_work(run))
    return run


def _recheck(ticket_id: int) -> RunStatus:
    """Re-run Boss on a ticket whose last payment was just approved, now or after the active run."""
    run = RunStatus(run_id=new_id(), ticket_id=ticket_id, trigger="recheck", status="queued", started_at=_now())
    if ACTIVE_RUN is None:
        return _start(run)
    RUNS[run.run_id] = run
    QUEUE.append(run)
    return run


async def _work(run: RunStatus) -> None:
    global ACTIVE_RUN
    try:
        result = (await run_board([run.ticket_id], run_id=run.run_id))[0]
        for p in result.pending_approvals:
            PENDING[p.id] = p
        _save_pending()
        run.result = result
        run.status = "error" if result.error else "done"
        run.error = result.error
    except Exception as exc:  # surface to the dashboard instead of dying silently
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"
    finally:
        run.finished_at = _now()
        ACTIVE_RUN = None
        if QUEUE:
            _start(QUEUE.pop(0))


@app.get("/api/runs")
async def runs() -> list[RunStatus]:
    return sorted(RUNS.values(), key=lambda r: r.started_at, reverse=True)


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str) -> RunStatus:
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id}.")
    return RUNS[run_id]


# ---------------------------------------------------------------- events


@app.get("/api/events")
async def events(
    limit: int = Query(100, ge=1, le=1000),
    since: str | None = Query(None, description="Only events after this ts (from a previous event)."),
    ticket_id: int | None = None,
    since_last_reset: bool = True,
) -> list[dict[str, Any]]:
    """Recent agent events, oldest first: what each agent said, the tools it called, and the results."""
    return read_events(limit=limit, since=since, ticket_id=ticket_id, since_last_reset=since_last_reset)


# ---------------------------------------------------------------- approvals


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="The human approving the payment.")


class DenyBody(BaseModel):
    denied_by: str = Field(min_length=1)
    reason: str = ""


@app.get("/api/approvals")
async def approvals(status: str | None = "pending") -> list[dict[str, Any]]:
    """Payment requests, each with a plain-English description built from the db (via MCP)."""
    items = [p for p in PENDING.values() if status is None or p.status == status]
    if not items:
        return []
    bills = await _mcp("list_bills_due")
    invoices = {i["id"]: i for i in bills["open_invoices"]}
    leases = {r["lease_id"]: r for r in bills["rent_due"]}
    return [{**p.model_dump(), "details": _describe(p, invoices, leases)} for p in items]


def _describe(p: PendingApproval, invoices: dict, leases: dict) -> dict[str, Any] | None:
    if p.tool == "pay_invoice" and (inv := invoices.get(p.args.get("invoice_id"))):
        late = f"{inv['days_overdue']} days overdue" if inv["days_overdue"] > 0 else f"due {inv['due_date']}"
        return {
            "title": f"Pay invoice #{inv['id']} to {inv['vendor_name']}",
            "amount": inv["amount"],
            "description": f"{inv['description']}. {late.capitalize()}. Paying it unblocks restocks from this vendor.",
        }
    if p.tool == "pay_rent" and (lease := leases.get(p.args.get("lease_id"))):
        days = -lease["days_overdue"]
        when = f"due {lease['next_due']}" + (f" (in {days} days)" if days > 0 else " (overdue)" if days < 0 else " (today)")
        return {
            "title": f"Pay rent for {lease['space_name']} to {lease['landlord']}",
            "amount": lease["monthly_rent"],
            "description": f"Monthly rent, {when}.",
        }
    return None  # the bill is no longer open; approving will be refused by the pay tool


def _pending(approval_id: str) -> PendingApproval:
    p = PENDING.get(approval_id)
    if p is None:
        raise HTTPException(404, f"No approval {approval_id}.")
    if p.status != "pending":
        raise HTTPException(409, f"Approval {approval_id} is already {p.status}.")
    return p


@app.post("/api/approvals/{approval_id}/approve")
async def approve_payment(approval_id: str, body: ApproveBody) -> dict[str, Any]:
    """The only route that moves cash. Runs the paused pay tool with the human's name.

    The MCP pay tool still applies its own checks (a real approver, an open bill,
    enough cash), so `ok` can be false even after approval.
    """
    p = await approve(_pending(approval_id), body.approved_by.strip())
    _save_pending()
    ok = bool(p.result and p.result.get("ok"))
    recheck = None
    if ok and p.ticket_id is not None and not any(
        q.ticket_id == p.ticket_id and q.status == "pending" for q in PENDING.values()
    ):
        recheck = _recheck(p.ticket_id)
    return {"ok": ok, "approval": p, "recheck_run": recheck}


@app.post("/api/approvals/{approval_id}/deny")
async def deny_payment(approval_id: str, body: DenyBody) -> dict[str, Any]:
    p = await deny(_pending(approval_id), body.denied_by.strip(), body.reason)
    _save_pending()
    return {"ok": True, "approval": p}


# ---------------------------------------------------------------- cash and reset


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts (read through list_bills_due)."""
    bills = await _mcp("list_bills_due")
    checking = next((a for a in bills["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {
        "date_today": bills["date_today"],
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["date"],
        "total_due": bills["total_due"],
        "cash_after_paying_all": bills["cash_after_paying_all"],
    }


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Copy the original db over the working copy and clear pending payment requests."""
    if ACTIVE_RUN is not None:
        raise HTTPException(409, "Cannot reset while a ticket run is working.")
    result = await reset_db()
    PENDING.clear()
    _save_pending()
    RUNS.clear()
    QUEUE.clear()
    return result
