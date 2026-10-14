# Campus Customs Multi-Agent Operations (Homework 5)

A pretend campus apparel shop run by a team of five AI agents. Open tickets (customer orders, rent, unpaid bills, discount requests) land on a board. The agents work them through an MCP server over a SQLite database, a FastAPI backend runs the team, and a React dashboard lets a human watch the agents and approve any payment.

```
React dashboard (frontend/, :5173)
        │  HTTP
FastAPI backend (backend/main.py, :8000) ── PydanticAI agent team (Boss, Inventory, Accounting, Facilities, Customer Service)
        │  MCP (stdio)
MCP server (mcp_server/server.py) ── data/campus_customs_new.db
```

## Folder layout

| Path | What it is |
|---|---|
| `AI_prompts.md` | Every prompt used with the AI coding assistant, grouped by problem |
| `data/campus_customs.db` | The original shop database (never written; used for resets) |
| `data/campus_customs_new.db` | The working copy the tools read and write. It is in its post-run state, matching the outputs below. |
| `mcp_server/` | FastMCP server with 16 tools (reads, payments, drafts, ticket updates, reset) |
| `backend/` | Agent team (`agents/`, `prompts/`, `models.py`, `llm.py`, `delegation.py`, `team.py`), human approval gate (`approvals.py`), audit trail (`audit.py`), and FastAPI routes (`main.py`) |
| `frontend/` | React + Vite + TypeScript dashboard |
| `output/` | Deliverables: harness, smoke test, ticket plan and reflection, design notes, results, screenshots, audit trail |

## Setup

Requires Python 3.12+ and Node 20+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then put your own PORTKEY_API_KEY in .env

cd frontend && npm install && cd ..
```

All agents use the `gpt-6-luna` model through Portkey. Never commit `.env`; `.gitignore` already excludes it.

## Run

Steps 2–4 each use their own terminal, with the venv active (`source .venv/bin/activate`) and starting from the `hw5/` folder.

### 1. Start from a clean database (when you need a clean run)

The tools only change `data/campus_customs_new.db`, the working copy. `data/campus_customs.db` is the original and is never written. To start over, copy the original over the working copy:

```bash
cp data/campus_customs.db data/campus_customs_new.db
rm -f output/pending_approvals.json    # clear any payment requests left from the last run
```

Do this while the backend is **stopped**. If the backend is already running, use **Reset shop** on the board (step 5) instead. It does the same copy through the `reset_shop_db` MCP tool, clears pending payments, and records the reset in the audit trail, so the board starts a fresh history.

### 2. Start the MCP server

You don't need a separate terminal for the MCP server. The backend starts `mcp_server/server.py` automatically over stdio when it starts (step 3) and keeps that one connection open while it runs. Both the agents and the backend use it.

To check the server on its own first:

```bash
fastmcp list mcp_server/server.py            # starts the server and lists its 16 tools
fastmcp dev inspector mcp_server/server.py   # optional: browse and call tools in the MCP Inspector (needs Node)
```

### 3. Start the FastAPI backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Run it from inside `backend/`, otherwise uvicorn can't find `main`. You should see `Application startup complete.`, and http://localhost:8000/api/health should return `{"ok":true,...}`. The full route list is in `output/harness.md`.

### 4. Start the React board

```bash
cd frontend
npm install        # first time only
npm run dev
```

Open http://localhost:5173. The port is fixed because it's the origin the backend allows. If something else is already using 5173, stop it first.

### 5. Reset the database before a full 3-ticket run

Always start a full run from the original data, so the cash and ticket statuses match the expected results:

1. On the board, press **Reset shop** and confirm. (Or, with the backend running: `curl -X POST http://localhost:8000/api/reset`.)
2. Check the board shows **$3,400** in checking and tickets **101, 102, 103** all **Open**, with "No approvals needed".
3. Type your name in **Approving as** (the pay tools refuse payments without a real person's name).
4. Run **101 first**, then **102**, then **103**. Ticket 101's invoice payment is what unblocks Bulldog Print Co, which 103's hoodie restock depends on. After each run, approve or deny the red payment request at the top. Approving a ticket's last payment starts Boss's automatic re-check of that ticket.

You can also run the team without the UI: `python -m backend.team --reset` resets the database and works every open ticket in the terminal, then asks you to approve each payment.

## Safety in short

- **Two checks on every payment.** Agents can only *request* `pay_invoice` / `pay_rent`. The backend pauses the call, and only a human clicking **Approve** runs it, with their name recorded as `approved_by`. The MCP pay tools also refuse blank or agent approvers, bills that are not open, and anything that would make cash negative.
- **Least privilege.** Each agent sees only its own tools. No agent can reset the database.
- **Nothing is sent.** Customer messages are saved as drafts only.
- **Facts come only from the database.** Agents read every fact through the MCP tools.
- **Everything is logged.** Every agent step, approval, and reset is appended to `output/audit_trail.json`.
- **Token limits.** Each ticket is capped at 16 model calls or 60k tokens, with at most 4 delegations, one run at a time.

Details: `output/harness.md` (tables, tools, agents, routes, dashboard, safety) and `output/design.md` (dashboard design).

## Results

| Ticket | Final status | Cash |
|---|---|---|
| 101 Bulldog tee | Needs info (vendor unblocked; customer must pick a size or wait) | −$840 (invoice 501, human-approved) |
| 102 Rent due | Resolved | −$2,400 (rent, human-approved) |
| 103 Bulk hoodie discount | Waiting on approval ($50 price and a 12-unit restock) | $0 |

Checking: $3,400 → $160. See `output/desk_tickets.html` (plan, what actually happened, cash, reflection), `output/resolved_tickets.json`, and `output/resolved_board.html` (dashboard screenshots). All three HTML files open with a double-click.
