"""Campus Customs MCP server.

Every tool reads data/campus_customs_new.db (the working copy). The original
data/campus_customs.db is only ever read, by reset_shop_db, so it stays clean.

Read tools return only what is in the database, plus simple date and quantity
math on those values. Write tools (payments, drafts, ticket updates, reset)
change only the working copy, and the pay tools refuse without a human approver
or when cash would go negative. Nothing is invented.
"""

import shutil
import sqlite3
from datetime import date
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Tools for the Campus Customs shop database. Use only the values these "
        "tools return; never invent data, prices, or vendors."
    ),
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _today(conn: sqlite3.Connection) -> str:
    return conn.execute("SELECT date_today FROM desk").fetchone()[0]


def _due_status(due: str, today: str) -> dict:
    """Days overdue (positive) or until due (negative), measured from desk.date_today."""
    days_overdue = (date.fromisoformat(today) - date.fromisoformat(due)).days
    if days_overdue > 0:
        status = "overdue"
    elif days_overdue == 0:
        status = "due_today"
    else:
        status = "upcoming"
    return {"days_overdue": days_overdue, "due_status": status}


def list_open_tickets() -> dict:
    """List every ticket on the board whose status is 'open', oldest first.

    Returns the shop's date_today and the raw ticket rows. Use
    get_ticket_details on a ticket id to see the rows it links to.
    """
    with _connect() as conn:
        return {
            "date_today": _today(conn),
            "tickets": _all(
                conn, "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at"
            ),
        }


def list_tickets() -> dict:
    """List every ticket on the board with its status (open, resolved, or in between), oldest first.

    Unlike list_open_tickets, resolved tickets stay in the list. For the dashboard.
    """
    with _connect() as conn:
        return {
            "date_today": _today(conn),
            "tickets": _all(conn, "SELECT * FROM tickets ORDER BY created_at"),
        }


def get_ticket_details(ticket_id: int) -> dict:
    """Get one ticket plus every database row it links to.

    Follows the ticket's links: sku/size -> inventory and pricing,
    invoice_id -> invoices and its vendor, lease_id -> leases. A linked row
    that does not exist is reported as not found rather than filled in.
    """
    with _connect() as conn:
        ticket = _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"error": f"No ticket with id {ticket_id}."}

        today = _today(conn)
        result: dict = {"date_today": today, "ticket": ticket}

        if ticket["sku"]:
            sku, size, qty = ticket["sku"], ticket["size"], ticket["qty"]
            if size:
                stock = _one(
                    conn,
                    "SELECT * FROM inventory WHERE sku = ? AND size = ?",
                    (sku, size),
                )
            else:
                stock = None
            result["inventory"] = stock or {
                "error": f"No inventory row for sku {sku} size {size}."
            }
            if stock and qty is not None:
                result["inventory"]["qty_requested"] = qty
                result["inventory"]["short_by"] = max(qty - stock["qty"], 0)
            result["all_sizes_in_stock"] = _all(
                conn, "SELECT size, qty, location FROM inventory WHERE sku = ?", (sku,)
            )
            result["pricing"] = _one(
                conn, "SELECT * FROM pricing WHERE sku = ?", (sku,)
            ) or {"error": f"No pricing row for sku {sku}."}

        if ticket["invoice_id"] is not None:
            invoice = _one(
                conn, "SELECT * FROM invoices WHERE id = ?", (ticket["invoice_id"],)
            )
            if invoice:
                invoice.update(_due_status(invoice["due_date"], today))
                result["invoice"] = invoice
                result["vendor"] = _one(
                    conn, "SELECT * FROM vendors WHERE id = ?", (invoice["vendor_id"],)
                ) or {"error": f"No vendor with id {invoice['vendor_id']}."}
            else:
                result["invoice"] = {
                    "error": f"No invoice with id {ticket['invoice_id']}."
                }

        if ticket["lease_id"] is not None:
            lease = _one(
                conn, "SELECT * FROM leases WHERE id = ?", (ticket["lease_id"],)
            )
            if lease:
                lease.update(_due_status(lease["next_due"], today))
                result["lease"] = lease
            else:
                result["lease"] = {"error": f"No lease with id {ticket['lease_id']}."}

        return result


def list_bills_due() -> dict:
    """List every open invoice and every lease's next rent, with cash on hand.

    Each bill shows days_overdue (positive = late, negative = days until due)
    measured from desk.date_today. Totals show whether cash covers every bill.
    Payments need human approval and are not made by this tool.
    """
    with _connect() as conn:
        today = _today(conn)
        invoices = _all(
            conn,
            """SELECT i.id, i.vendor_id, v.name AS vendor_name, i.amount,
                      i.due_date, i.status, i.description
               FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
               WHERE i.status = 'open' ORDER BY i.due_date""",
        )
        for inv in invoices:
            inv.update(_due_status(inv["due_date"], today))

        rent = _all(
            conn,
            """SELECT id AS lease_id, space_name, landlord, monthly_rent, next_due
               FROM leases ORDER BY next_due""",
        )
        for lease in rent:
            lease.update(_due_status(lease["next_due"], today))

        accounts = _all(conn, "SELECT * FROM cash_accounts")
        cash = sum(a["balance"] for a in accounts)
        total_due = sum(i["amount"] for i in invoices) + sum(
            r["monthly_rent"] for r in rent
        )
        return {
            "date_today": today,
            "open_invoices": invoices,
            "rent_due": rent,
            "cash_accounts": accounts,
            "total_due": total_due,
            "cash_after_paying_all": cash - total_due,
            "cash_covers_all": cash >= total_due,
        }


# ---------------------------------------------------------------- write helpers

ORIGINAL_DB_PATH = DB_PATH.parent / "campus_customs.db"

# Names that can never count as a human approver.
NOT_HUMAN = {"", "boss", "inventory", "accounting", "facilities", "customer_service",
             "customer service", "agent", "ai", "assistant", "system", "auto", "model"}

TICKET_STATUSES = ("open", "waiting_on_approval", "blocked", "needs_info", "resolved")
DRAFT_AUDIENCES = ("customer", "landlord", "vendor")


def _connect_rw() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Working database not found: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_drafts(conn: sqlite3.Connection) -> None:
    """The drafts table lives only in the working copy; a reset removes it."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS drafts (
               id INTEGER PRIMARY KEY,
               ticket_id INTEGER NOT NULL REFERENCES tickets(id),
               author TEXT NOT NULL,
               audience TEXT NOT NULL,
               recipient TEXT NOT NULL,
               body TEXT NOT NULL,
               status TEXT NOT NULL DEFAULT 'draft',
               created_at TEXT NOT NULL
           )"""
    )


def _approver_problem(approved_by: str) -> str | None:
    if approved_by.strip().lower() in NOT_HUMAN:
        return "a named human approver is required (approved_by); agents cannot approve payments."
    return None


def _add_month(iso: str) -> str:
    d = date.fromisoformat(iso)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    raise ValueError(iso)


def _pay(conn: sqlite3.Connection, kind: str, ref_id: int, amount: float,
         account: str, approved_by: str) -> dict:
    """Move cash out of one account and record the payment. Caller holds the transaction."""
    acct = _one(conn, "SELECT * FROM cash_accounts WHERE name = ?", (account,))
    if acct is None:
        return {"ok": False, "refused": f"No cash account named {account!r}."}
    if acct["balance"] < amount:
        return {
            "ok": False,
            "refused": f"Not enough cash: {account} has {acct['balance']}, payment is {amount}. "
                       "Balances may not go negative.",
        }
    today = _today(conn)
    new_balance = acct["balance"] - amount
    conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                 (new_balance, today, account))
    cur = conn.execute(
        "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (kind, ref_id, amount, account, today, approved_by.strip()),
    )
    return {
        "ok": True,
        "payment": _one(conn, "SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)),
        "balance_before": acct["balance"],
        "balance_after": new_balance,
    }


# ---------------------------------------------------------------- accounting


def pay_invoice(invoice_id: int, approved_by: str = "", account: str = "checking") -> dict:
    """Pay one open vendor invoice. REQUIRES HUMAN APPROVAL.

    Refuses unless approved_by names a human, the invoice is open, and the
    account has enough cash (no negative balances). On success it marks the
    invoice paid, takes the amount out of cash_accounts, and adds a payments row.
    """
    if problem := _approver_problem(approved_by):
        return {"ok": False, "refused": problem}
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        invoice = _one(conn, "SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        if invoice is None:
            result = {"ok": False, "refused": f"No invoice with id {invoice_id}."}
        elif invoice["status"] != "open":
            result = {"ok": False, "refused": f"Invoice {invoice_id} is {invoice['status']}, not open."}
        else:
            result = _pay(conn, "invoice", invoice_id, invoice["amount"], account, approved_by)
            if result["ok"]:
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
                result["invoice"] = _one(conn, "SELECT * FROM invoices WHERE id = ?", (invoice_id,))
        conn.execute("COMMIT" if result["ok"] else "ROLLBACK")
        return result
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def check_margin(sku: str, unit_price: float | None = None, qty: int = 1) -> dict:
    """Margin math for a SKU at list price or a proposed unit price.

    Uses pricing.unit_cost and pricing.list_price only. Reports per-unit and
    total margin, the discount versus list, and whether the price is above cost.
    The database has no discount policy; any price below list needs human approval.
    """
    with _connect() as conn:
        p = _one(conn, "SELECT * FROM pricing WHERE sku = ?", (sku,))
        if p is None:
            return {"error": f"No pricing row for sku {sku}."}
        price = p["list_price"] if unit_price is None else unit_price
        unit_margin = price - p["unit_cost"]
        return {
            "sku": sku,
            "unit_cost": p["unit_cost"],
            "list_price": p["list_price"],
            "unit_price": price,
            "qty": qty,
            "discount_vs_list_pct": round((p["list_price"] - price) / p["list_price"] * 100, 2),
            "unit_margin": round(unit_margin, 2),
            "margin_pct": round(unit_margin / price * 100, 2) if price else None,
            "total_revenue": round(price * qty, 2),
            "total_cost": round(p["unit_cost"] * qty, 2),
            "total_margin": round(unit_margin * qty, 2),
            "above_cost": price > p["unit_cost"],
        }


def list_payments() -> dict:
    """Every payment already made, newest first. Check here before prepping a payment twice."""
    with _connect() as conn:
        return {"date_today": _today(conn),
                "payments": _all(conn, "SELECT * FROM payments ORDER BY id DESC")}


# ---------------------------------------------------------------- facilities


def pay_rent(lease_id: int, approved_by: str = "", account: str = "checking") -> dict:
    """Pay the next rent on one lease. REQUIRES HUMAN APPROVAL.

    Refuses unless approved_by names a human and the account has enough cash
    (no negative balances). On success it takes monthly_rent out of
    cash_accounts, adds a payments row, and moves leases.next_due forward one month.
    """
    if problem := _approver_problem(approved_by):
        return {"ok": False, "refused": problem}
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        lease = _one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if lease is None:
            result = {"ok": False, "refused": f"No lease with id {lease_id}."}
        else:
            result = _pay(conn, "rent", lease_id, lease["monthly_rent"], account, approved_by)
            if result["ok"]:
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?",
                             (_add_month(lease["next_due"]), lease_id))
                result["rent_period_paid"] = lease["next_due"]
                result["lease"] = _one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        conn.execute("COMMIT" if result["ok"] else "ROLLBACK")
        return result
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_lease(lease_id: int) -> dict:
    """One lease with days until rent is due (negative) or overdue (positive)."""
    with _connect() as conn:
        lease = _one(conn, "SELECT * FROM leases WHERE id = ?", (lease_id,))
        if lease is None:
            return {"error": f"No lease with id {lease_id}."}
        today = _today(conn)
        lease.update(_due_status(lease["next_due"], today))
        return {"date_today": today, "lease": lease}


# ---------------------------------------------------------------- inventory


def _vendor_with_invoices(conn: sqlite3.Connection, vendor: dict, today: str) -> dict:
    open_invoices = _all(
        conn,
        "SELECT id, amount, due_date, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor["id"],),
    )
    for inv in open_invoices:
        inv.update(_due_status(inv["due_date"], today))
    return {**vendor, "open_invoices": open_invoices, "blocked": bool(open_invoices)}


def check_stock(sku: str, size: str | None = None) -> dict:
    """Stock on hand for a SKU, for one size or every size, with aisle location."""
    with _connect() as conn:
        if size:
            rows = _all(conn, "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size))
        else:
            rows = _all(conn, "SELECT * FROM inventory WHERE sku = ? ORDER BY size", (sku,))
        if not rows:
            return {"error": f"No inventory rows for sku {sku}" + (f" size {size}." if size else ".")}
        return {"sku": sku, "name": rows[0]["name"], "stock": rows,
                "total_on_hand": sum(r["qty"] for r in rows)}


def find_restock_vendors(sku: str) -> dict:
    """Every vendor that could restock a SKU, with lead_days and whether it is blocked.

    The database has no SKU-to-vendor table, so this lists all vendors with
    their specialty and flags any that appear on a past or open invoice for
    this SKU (supplied_this_sku). A vendor with an open invoice is blocked: it
    will not ship until that invoice is paid.
    """
    with _connect() as conn:
        item = _one(conn, "SELECT DISTINCT sku, name FROM inventory WHERE sku = ?", (sku,))
        if item is None:
            return {"error": f"No inventory rows for sku {sku}."}
        today = _today(conn)
        supplied = {r["vendor_id"] for r in _all(
            conn, "SELECT DISTINCT vendor_id FROM invoices WHERE description LIKE ?", (f"%{sku}%",)
        )}
        vendors = [
            {**_vendor_with_invoices(conn, v, today), "supplied_this_sku": v["id"] in supplied}
            for v in _all(conn, "SELECT * FROM vendors ORDER BY id")
        ]
        return {"date_today": today, "sku": sku, "name": item["name"], "vendors": vendors}


def get_vendor_status(vendor_id: int) -> dict:
    """One vendor with lead_days, its open invoices, and whether it is blocked from shipping."""
    with _connect() as conn:
        vendor = _one(conn, "SELECT * FROM vendors WHERE id = ?", (vendor_id,))
        if vendor is None:
            return {"error": f"No vendor with id {vendor_id}."}
        today = _today(conn)
        return {"date_today": today, "vendor": _vendor_with_invoices(conn, vendor, today)}


# ---------------------------------------------------------------- customer service


def save_draft(ticket_id: int, audience: str, body: str, author: str = "customer_service") -> dict:
    """Save a message draft on the board. Nothing is ever sent.

    audience is 'customer', 'landlord', or 'vendor'. The recipient is the
    ticket's requester, taken from the tickets table.
    """
    if audience not in DRAFT_AUDIENCES:
        return {"ok": False, "refused": f"audience must be one of {DRAFT_AUDIENCES}."}
    if not body.strip():
        return {"ok": False, "refused": "body is empty."}
    conn = _connect_rw()
    try:
        ticket = _one(conn, "SELECT id, requester FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"ok": False, "refused": f"No ticket with id {ticket_id}."}
        _ensure_drafts(conn)
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, author, audience, recipient, body, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ticket_id, author, audience, ticket["requester"], body.strip(), _today(conn)),
        )
        return {"ok": True, "draft": _one(conn, "SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,))}
    finally:
        conn.close()


# ---------------------------------------------------------------- boss / board


def update_ticket(ticket_id: int, status: str | None = None, note: str | None = None,
                  author: str = "boss") -> dict:
    """Set a ticket's status and/or add a dated note to it.

    status is one of open, waiting_on_approval, blocked, needs_info, resolved.
    Notes are added to the end of tickets.notes, stamped with desk.date_today.
    """
    if status is not None and status not in TICKET_STATUSES:
        return {"ok": False, "refused": f"status must be one of {TICKET_STATUSES}."}
    if status is None and not (note and note.strip()):
        return {"ok": False, "refused": "Give a status, a note, or both."}
    conn = _connect_rw()
    try:
        ticket = _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        if ticket is None:
            return {"ok": False, "refused": f"No ticket with id {ticket_id}."}
        notes = ticket["notes"] or ""
        if note and note.strip():
            stamp = f"[{_today(conn)} {author}] {note.strip()}"
            notes = f"{notes}\n{stamp}" if notes else stamp
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
                     (status or ticket["status"], notes, ticket_id))
        return {"ok": True, "ticket": _one(conn, "SELECT * FROM tickets WHERE id = ?", (ticket_id,))}
    finally:
        conn.close()


def reset_shop_db(confirm: bool = False) -> dict:
    """Copy the original campus_customs.db over the working copy. For the backend only.

    Wipes every payment, ticket update, and draft made since the last reset.
    Refuses unless confirm is true.
    """
    if not confirm:
        return {"ok": False, "refused": "Pass confirm=true to reset the working database."}
    shutil.copyfile(ORIGINAL_DB_PATH, DB_PATH)
    with _connect() as conn:
        return {"ok": True, "date_today": _today(conn),
                "open_tickets": conn.execute(
                    "SELECT COUNT(*) FROM tickets WHERE status = 'open'").fetchone()[0],
                "cash": _all(conn, "SELECT * FROM cash_accounts")}


def get_board_summary() -> dict:
    """Ticket counts by status, cash on hand, money owed, and draft count, for the dashboard."""
    with _connect() as conn:
        has_drafts = _one(conn, "SELECT name FROM sqlite_master WHERE type='table' AND name='drafts'")
        return {
            "date_today": _today(conn),
            "tickets_by_status": {r["status"]: r["n"] for r in _all(
                conn, "SELECT status, COUNT(*) AS n FROM tickets GROUP BY status")},
            "cash_on_hand": conn.execute("SELECT COALESCE(SUM(balance), 0) FROM cash_accounts").fetchone()[0],
            "open_invoice_total": conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM invoices WHERE status = 'open'").fetchone()[0],
            "next_rent_total": conn.execute(
                "SELECT COALESCE(SUM(monthly_rent), 0) FROM leases").fetchone()[0],
            "payments_made": conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0],
            "drafts": conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0] if has_drafts else 0,
        }


for _tool in (
    list_open_tickets, get_ticket_details, list_bills_due,
    pay_invoice, check_margin, list_payments,
    pay_rent, get_lease,
    check_stock, find_restock_vendors, get_vendor_status,
    save_draft,
    update_ticket, reset_shop_db, get_board_summary, list_tickets,
):
    mcp.tool(_tool)


if __name__ == "__main__":
    mcp.run()
