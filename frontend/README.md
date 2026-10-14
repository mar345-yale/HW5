# Campus Customs · Agent Desk (frontend)

React + Vite + TypeScript dashboard for the Campus Customs agent team. It calls the FastAPI backend at `http://localhost:8000` (override with `VITE_API_URL`).

## Run

1. Start the backend (from `Homework-5/backend/`, with the venv active):

   ```
   uvicorn main:app --reload --port 8000
   ```

2. Start the board (from `Homework-5/frontend/`):

   ```
   npm install   # first time only
   npm run dev
   ```

   Open http://localhost:5173. The port is fixed to 5173 because that is the origin the backend allows. If another app is already on 5173, stop it first.

## What's on the board

- **Approval bar (top):** each payment an agent asked for, with a glowing red **Approve** button and a plain description of the payment. Only this button moves cash. When a ticket's last payment is approved, Boss automatically re-checks that ticket.
- **Checking balance (top right):** from `cash_accounts`; it pulses when it changes.
- **Tickets:** all three tickets with their live status. Pick one and press **Start agent team**.
- **The team:** the five agents as emoji. They glow while working, and show "Waiting" while a teammate they asked is working.
- **Live activity:** what each agent said and which tools it used, read from `output/audit_trail.json` through `/api/events`.
- **What each agent did:** Boss's final call plus a one-line recap and the tools for each agent on that ticket.
- **Reset shop:** restores the original database for a fresh run.

## Code map

| File | Role |
|---|---|
| `src/App.tsx` | Page layout, polling (every 1.5 s during a run, 5 s otherwise), and actions |
| `src/api.ts` | Calls to the backend routes |
| `src/describe.ts` | Turns audit events into readable lines, live agent states, and summaries |
| `src/agents.ts` | Agent names, emoji, and labels |
| `src/components/` | Approval bar, cash card, ticket list, agent team, activity feed, summary |
