# Campus Customs MCP Server

This server gives the Campus Customs agent team (Boss, Inventory, Accounting, Facilities, Customer Service) and the backend one shared set of tools for the shop database. Every shop fact and every change goes through these tools, so everyone works from the same data. The tools return only what is in the database, so agents have no reason to invent data or prices.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy. Read tools open it read-only; write tools change only this file.
- **Never written:** `data/campus_customs.db`, the original. `reset_shop_db` copies it over the working copy.
- **Drafts:** the `drafts` table exists only in the working copy. It is created the first time a draft is saved, and a reset removes it.

## Tools

| Tool | Used by | What it does |
|---|---|---|
| `list_open_tickets()` | all agents | `desk.date_today` and every ticket with status `open`, oldest first. |
| `get_ticket_details(ticket_id)` | all agents | One ticket plus every row it links to (inventory, pricing, invoice, vendor, lease), with shortfalls and days overdue. |
| `list_bills_due()` | all agents | Open invoices and lease rent with days overdue, plus cash on hand and whether it covers every bill. |
| `pay_invoice(invoice_id, approved_by)` | Accounting, after human approval | Pays an open invoice: marks it paid, takes cash out, and adds a `payments` row. |
| `check_margin(sku, unit_price, qty)` | Accounting | Margin per unit and in total at list price or a proposed price, and whether it is above cost. |
| `list_payments()` | Accounting | Every payment made so far. |
| `get_vendor_status(vendor_id)` | Accounting, Inventory | One vendor with its open invoices and whether it is blocked from shipping. |
| `pay_rent(lease_id, approved_by)` | Facilities, after human approval | Pays a lease's `monthly_rent`, adds a `payments` row, and moves `next_due` forward one month. |
| `get_lease(lease_id)` | Facilities | One lease with days until due or overdue. |
| `check_stock(sku, size)` | Inventory | Stock on hand for one size or every size of a SKU. |
| `find_restock_vendors(sku)` | Inventory | Every vendor with `lead_days`, whether it is blocked, and whether it has supplied this SKU. |
| `save_draft(ticket_id, audience, body)` | backend | Saves a message draft to the `drafts` table. Nothing is ever sent. |
| `update_ticket(ticket_id, status, note)` | backend | Sets a ticket's status and adds a dated note. |
| `get_board_summary()` | backend | Ticket counts by status, cash, money owed, payments, and drafts. |
| `list_tickets()` | backend | Every ticket with its status, including resolved ones (for the dashboard). |
| `reset_shop_db(confirm)` | backend only | Copies the original database over the working copy. Refuses unless `confirm=true`. |

## Payment safeguards

1. **In this server:** `pay_invoice` and `pay_rent` refuse without a named human in `approved_by`. Blank values and agent names (`accounting`, `boss`, and so on) are rejected. They also refuse a bill that is not open, and any payment that would make a balance negative.
2. **In the backend:** agents never see `approved_by`. When an agent calls a pay tool, the call is paused and queued as a pending approval. Only `backend/approvals.py` can run it, after a human approves, with that person's name as `approved_by`.

## Run

The backend starts this server over stdio. To try it on its own, from the project folder with the venv active:

```
fastmcp list mcp_server/server.py            # start it and list the 16 tools
fastmcp dev inspector mcp_server/server.py   # optional: MCP Inspector in the browser (needs Node)
```
