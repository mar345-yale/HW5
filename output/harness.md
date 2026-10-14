# Campus Customs — Agent Harness

The tools read and write `data/campus_customs_new.db`, which is a working copy. `data/campus_customs.db` is the original and is never written to. To reset before a full run, use `python -m backend.team --reset`, which calls the `reset_shop_db` MCP tool to copy the original over the working copy.

## Tables

### desk
- Fields: `date_today`, `notes`
- Why it matters: `date_today` is "today" for the shop. All agents use it to decide what is overdue or due soon.

### tickets
- Fields: `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id`, `invoice_id`, `status`, `notes`, `created_at`
- Why it matters: This is the work board. Boss reads each open ticket and routes it, and the links (`sku`/`size`, `lease_id`, `invoice_id`) tell the agents which tables to check.

### inventory
- Fields: `sku`, `name`, `size`, `qty`, `location`
- Why it matters: Inventory uses it to check stock by SKU and size and to find shortfalls against a ticket's `qty`.

### pricing
- Fields: `sku`, `unit_cost`, `list_price`
- Why it matters: Accounting uses it to check margins on discount requests and to price purchase orders. These are the only real prices, so the agents must not invent any.

### vendors
- Fields: `id`, `name`, `specialty`, `lead_days`
- Why it matters: Inventory uses it to pick who can restock (by `specialty`) and how long it will take (`lead_days`).

### invoices
- Fields: `id`, `vendor_id`, `amount`, `due_date`, `status`, `description`
- Why it matters: An `open` invoice blocks that vendor from shipping. Accounting compares `due_date` with `desk.date_today` to find overdue bills and preps them for payment.

### leases
- Fields: `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes`
- Why it matters: Facilities uses it to handle rent. `monthly_rent` is the amount to prep for approval, and `next_due` moves forward one month after payment.

### cash_accounts
- Fields: `name`, `balance`, `date`
- Why it matters: This is the only cash source. The pay tool checks `balance` first and refuses any payment that would make it negative.

### payments
- Fields: `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by`
- Why it matters: This is the record of human-approved payments. Each one is a row here, with `kind` and `ref_id` pointing at the invoice or lease that was paid.

### drafts (added in Problem 5, working copy only)
- Fields: `id`, `ticket_id`, `author`, `audience`, `recipient`, `body`, `status`, `created_at`
- Why it matters: Customer and landlord messages are saved here as drafts and never sent. `recipient` comes from `tickets.requester`. `save_draft` creates the table the first time it runs, and a reset removes it.

## Agents

All five agents use `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`). Every agent can `delegate` to any other agent, and every agent sees the three shared read tools (`list_open_tickets`, `get_ticket_details`, `list_bills_due`) plus its own tools below.

| Agent | Role | Prompt / code | Own MCP tools | Returns |
|---|---|---|---|---|
| Boss | Reads each ticket, routes work, makes the final call | `backend/prompts/boss.md`, `backend/agents/boss.py` | shared tools only | `TicketDecision` |
| Inventory | Stock by SKU and size, shortfalls, restock vendor, lead time | `backend/prompts/inventory.md`, `backend/agents/inventory.py` | `check_stock`, `find_restock_vendors`, `get_vendor_status` | `AgentReport` |
| Accounting | Cash, invoices, margins, invoice payments (approval only) | `backend/prompts/accounting.md`, `backend/agents/accounting.py` | `pay_invoice`, `check_margin`, `list_payments`, `get_vendor_status` | `AgentReport` |
| Facilities | Lease, rent, landlord notices, rent payment (approval only) | `backend/prompts/facilities.md`, `backend/agents/facilities.py` | `pay_rent`, `get_lease` | `AgentReport` |
| Customer Service | Drafts messages to customers and requesters | `backend/prompts/customer_service.md`, `backend/agents/customer_service.py` | shared tools only | `AgentReport` |

The backend (not an agent) calls `save_draft`, `update_ticket`, `get_board_summary`, `list_tickets`, and `reset_shop_db` through the same MCP connection.

## MCP Tools

All 16 tools live in `mcp_server/server.py` and use only `data/campus_customs_new.db`. R = reads the table, W = writes to it.

| Tool | Used by | Tables |
|---|---|---|
| `list_open_tickets()` | all agents | tickets (R), desk (R) |
| `get_ticket_details(ticket_id)` | all agents | tickets, inventory, pricing, invoices, vendors, leases, desk (all R) |
| `list_bills_due()` | all agents | invoices, vendors, leases, cash_accounts, desk (all R) |
| `pay_invoice(invoice_id, approved_by)` | Accounting, after human approval | invoices (R/W), cash_accounts (R/W), payments (W), desk (R) |
| `check_margin(sku, unit_price, qty)` | Accounting | pricing (R) |
| `list_payments()` | Accounting | payments (R), desk (R) |
| `get_vendor_status(vendor_id)` | Accounting, Inventory | vendors (R), invoices (R), desk (R) |
| `pay_rent(lease_id, approved_by)` | Facilities, after human approval | leases (R/W), cash_accounts (R/W), payments (W), desk (R) |
| `get_lease(lease_id)` | Facilities | leases (R), desk (R) |
| `check_stock(sku, size)` | Inventory | inventory (R) |
| `find_restock_vendors(sku)` | Inventory | inventory (R), vendors (R), invoices (R), desk (R) |
| `save_draft(ticket_id, audience, body)` | backend | drafts (W, created if missing), tickets (R), desk (R) |
| `update_ticket(ticket_id, status, note)` | backend | tickets (R/W), desk (R) |
| `get_board_summary()` | backend | tickets, cash_accounts, invoices, leases, payments, drafts, desk (all R) |
| `list_tickets()` | backend (dashboard) | tickets (R), desk (R) |
| `reset_shop_db(confirm)` | backend only | every table: copies `campus_customs.db` over the working copy |

### How the first three tools unlock the tickets

#### list_open_tickets()
- Tables read: `tickets`, `desk`
- Tickets it helps unlock: #101, #102, #103
- Why it fits:
  - **#101:** It puts the tee order on the board with its `invoice_id`, which signals that a payment problem sits behind a simple customer order.
  - **#102:** It surfaces the rent notice and its `lease_id`, so Boss knows to route it to Facilities and Accounting.
  - **#103:** It shows the hoodie request as a `price_override` with `qty` 20, so Boss knows a margin decision and a stock check are both needed.

#### get_ticket_details(ticket_id)
- Tables read: `tickets`, `desk`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`
- Tickets it helps unlock: #101, #102, #103
- Why it fits:
  - **#101:** In one call it shows the tee is out of stock in size S and that invoice 501 to Bulldog Print Co is 3 days overdue, which is what blocks the restock.
  - **#102:** It follows `lease_id` to the Chapel Street lease and shows the real $2,400 rent and that it is due in 2 days.
  - **#103:** It shows the 12-hoodie shortfall in size M along with `unit_cost` and `list_price`, which Accounting needs to judge a bulk discount without inventing prices.

#### list_bills_due()
- Tables read: `invoices`, `vendors`, `leases`, `cash_accounts`, `desk`
- Tickets it helps unlock: #101, #102
- Why it fits:
  - **#101:** It shows invoice 501 as overdue next to the cash balance, so Accounting can prep the payment that unblocks the vendor.
  - **#102:** It puts the rent beside every other bill and the $3,400 balance, so Accounting can confirm cash covers rent before asking for human approval.

## Backend Routes

FastAPI app in `backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000`; every URL below is under `http://localhost:8000`.

- `GET /api/health`: checks that the server is up and shows any run in progress.
- `GET /api/tickets`: lists every ticket with its status and whether it is open or resolved.
- `POST /api/tickets/{id}/run`: starts the agent team on one ticket in the background and returns a `run_id`; only one run can go at a time.
- `GET /api/runs`: lists every run since the server started, newest first.
- `GET /api/runs/{run_id}`: shows whether a run is still going, plus its decision, payment requests, and tokens used.
- `GET /api/events`: returns recent agent events (what each agent said, the tools it called, and the results); `?since=`, `?ticket_id=`, and `?limit=` narrow it down. By default it only returns events since the last reset (`?since_last_reset=false` returns everything).
- `GET /api/approvals`: lists payment requests waiting for a human, each with a plain-English title, amount, and description built from the database.
- `POST /api/approvals/{id}/approve`: a human approves a payment; the pay tool runs and cash changes. This is the only route that moves cash. After a ticket's last pending payment is approved, Boss automatically re-checks that ticket (or the re-check waits its turn if another run is going).
- `POST /api/approvals/{id}/deny`: a human turns down a payment; nothing is paid.
- `GET /api/cash`: shows the current checking balance from `cash_accounts`.
- `POST /api/reset`: copies the original database over the working copy and clears pending payments; refused while a run is going.

## Dashboard

React + Vite + TypeScript app in `frontend/`. Start it from `frontend/` with `npm run dev` and open http://localhost:5173 (the port is fixed because that is the origin the backend allows). It talks only to the backend routes above, so it never touches the database or the agents directly. Design reasons are in `output/design.md`.

| Part of the board | What it shows | Route(s) it uses |
|---|---|---|
| Header | Shop date, **checking balance** (pulses when it changes), "left if all paid", and **Reset shop** | `GET /api/cash`, `POST /api/reset` |
| Approval bar (top) | Each payment an agent asked for: a glowing red **Approve $amount** button, a plain description, who asked, and the ticket. A quiet green "No approvals needed" bar when there are none. | `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `.../deny` |
| Tickets (left) | All three tickets with live status chips: Open, Agents working, Waiting on approval, Needs info, Resolved | `GET /api/tickets`, `GET /api/runs` |
| Selected ticket | **Start agent team** / **Run agent team again** button (one run at a time) | `POST /api/tickets/{id}/run` |
| The team | The five agents as emoji (Boss 🤵👔, Inventory 🧑‍🏭📦, Accounting 🤓🧮, Facilities 👷🏢, Customer Service 😊🎧). Working agents glow blue; an agent waiting on a teammate gets a soft ring; finished agents show Done. | `GET /api/events` |
| Live activity | Every step of the latest run in plain English: tasks, delegations, tool calls, decisions, payment requests, board saves | `GET /api/events` |
| What each agent did | Boss's final call (plus the saved customer draft) and a one-line recap with tool pills for each agent | `GET /api/events` |

- **Live updates:** the board polls every 1.5 seconds while a run is going and every 5 seconds otherwise. Polling only reads the backend, so it uses no tokens.
- **Links:** `http://localhost:5173/?ticket=101` opens the board on a specific ticket.

### Known limits (seen in Problem 9)
- Only payments (`pay_invoice`, `pay_rent`) can be approved from the board. A price decision or a restock (ticket 103's $50 price and 12-unit restock) shows up in Boss's call but has no approve button, so the ticket stays "Waiting on approval" until a route for those decisions is added.
- "Needs info" (ticket 101) waits on the customer. The board has no way to record the customer's answer yet.

## Audit Trail

Every agent-loop step is appended to `output/audit_trail.json` (`backend/audit.py`). The file is a JSON array that only grows; a new run never wipes it. Each record has a timestamp, `ticket_run_id`, `ticket_id`, `agent`, `agent_run_id`, the delegation `chain`, and the `step`:

- `user_prompt`: an agent run starts.
- `model_request`: the prompt, tool results, and retry prompts sent to the model.
- `model_response`: the model's text and tool calls (with arguments), the model name, and tokens used.
- `end`: the final report, decision, or paused payment request.
- `error`: what stopped the run, for example the usage cap.

The backend also records `board_write` (ticket updates and drafts), `ticket_done` (status and token totals), `payment_decision` (who approved or denied which payment, and the pay tool's reply), and `reset`.

## Safety

### Guardrails already in place
- **Payments need two separate checks.** The MCP pay tools refuse without a named human approver, refuse a bill that is not open, and refuse anything that would make a balance negative. Separately, the backend pauses every agent pay call, and only `backend/approvals.py` can run it after a human approves.
- **Least privilege.** Each agent sees only its own tools. Agents cannot fill in `approved_by`. No agent can reset the database, update tickets, or save drafts.
- **Nothing leaves the shop.** Messages are saved as drafts. No tool can email anyone or contact a vendor.
- **Facts come only from the database, through MCP.** Prompts forbid invented data, and the backend writes go through the same MCP tools.
- **Work on a copy.** Agents only change `campus_customs_new.db`. The original stays clean for resets, and every change is in the audit trail.
- **A real name on every approval.** The dashboard's approve button asks for the approver's name, and the pay tool still refuses blanks and agent names. A refused approval stays pending so a person can retry or deny it.
- **Honest statuses.** A ticket is only marked resolved by Boss. After a payment, Boss re-checks the ticket instead of the board assuming it is done.
- **One run at a time.** The backend refuses a second run, and reset is refused while a run is going, so the database can't change underneath the agents.
- **Local only.** The backend only accepts browser calls from localhost pages (the Vite board on port 5173).
- **The coding assistant is fenced too.** `.claude/settings.json` at the repo root denies Claude Code the `pay_invoice`, `pay_rent`, and `reset_shop_db` MCP tools, so only the dashboard's human approval flow can move cash.

### What a real business would add for real customers and real money
- **Real identity for approvers.** Approvers should sign in with SSO and roles, not type a name. Above a dollar threshold, two people should have to approve.
- **Spending limits.** Cap each payment and each day's total. Pay only vendors on an approved list, and verify any change to a vendor's bank details outside the system.
- **No double payments.** Give each payment a unique key so the same bill can't be paid twice, and reconcile daily against the bank.
- **A human sends every customer message.** Agents can't promise prices, discounts, or dates without approval. Keep customer personal data out of prompts where possible, and follow opt-out and privacy rules.
- **Treat ticket text as untrusted.** A customer's note could contain instructions aimed at the agents. Agents should treat it as data and never follow it.
- **Tamper-proof logs and alerts.** Ship the audit trail to write-once storage. Alert on refused payments, usage-cap hits, and unusual activity. Keep a kill switch that stops all agents.
- **Staged rollout.** Run in shadow mode before giving agents write access, and replay past tickets as a test suite whenever prompts or models change.

### Token limits
- **Per-ticket cap:** 16 model requests or 60,000 tokens, shared by every agent on the ticket (`TICKET_USAGE_LIMITS`).
- **Delegation limits:** a chain can go at most Boss → specialist → specialist, with at most 4 delegations per ticket. Agents can't delegate to themselves or loop back up the chain.
- **Short answers:** replies are capped at 1,200 tokens for specialists and 1,800 for Boss, with low reasoning effort and short structured outputs.
- **Less to send:** the backend fetches each ticket once without the model and passes it along. Each agent sees only its own tools, so its prompt is smaller. A stable cache key per agent lets the prompt be reused.
- **No model calls for board writes:** ticket updates and drafts are saved by the backend, not the agents.
- **One ticket at a time**, so the per-ticket cap holds.
- **For a real business:** a daily budget (`UsageLimits.cost_limit`) with alerts, a cheaper model for simple routing, and a cost-per-ticket report built from the audit trail.
