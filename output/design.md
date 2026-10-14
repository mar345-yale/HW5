# Campus Customs Agent Desk: Design Choices

The dashboard (`frontend/`) lets one person watch five AI agents work the shop's tickets and step in only when money has to move. Every design choice below serves one goal: **someone who has never seen the system should know, at a glance, what the agents are doing and what is waiting on them.**

## Look and feel

| Choice | What we did | Why |
|---|---|---|
| Colors | White cards on a very light blue page (`#f4f7ff`). One main blue (`#2563eb`) for actions, headings, and "working". Green for resolved, amber for waiting on approval, red only for the approval button and errors. | Blue and white reads calm and trustworthy, which suits a tool about money. With so little color used, the few non-blue colors stand out, so each one carries a meaning. |
| Soft edges | Every surface is rounded: cards 20px, buttons and chips fully rounded (pill shaped). Light blue-tinted shadows instead of hard borders. | You asked for no harsh edges. Rounded, shadowed cards also feel friendly, and the cards stand apart from the page without heavy lines. |
| Type | System sans-serif font, bold headings, small uppercase blue section labels ("THE TEAM", "LIVE ACTIVITY"). | Clean and familiar. The labels let you scan the page by section without reading every line. |

## Layout (top to bottom)

1. **Header:** shop name, the shop's date (`desk.date_today`), the **checking balance** card, and **Reset shop**.
2. **Approval bar:** always the first thing under the header, full width.
3. **Two columns:**
   - **Left:** the three tickets.
   - **Right:** the selected ticket. It shows the ticket header and **Start agent team** button, then the five agents in a row, then **Live activity** and **What each agent did** side by side.

**Why this order:** it follows the order of urgency.
- **Money first.** Cash and approvals are the only things that need a human, so they sit at the top and never scroll away.
- **Then the queue of work.** The tickets list sits on the left, the way inboxes do.
- **Then the detail.** The team, the live log, and the recap for the selected ticket fill the right side.

On narrow screens the columns stack, and the agent row wraps to three across.

## The approval button

- **What it looks like:** a **glowing red pill** labeled with the dollar amount ("Approve $2,400"). It pulses with a soft red glow.
- **What's next to it:** a plain-English line built from the database: *"Pay rent for Chapel Street shop to Elm City Properties. Monthly rent, due 2026-09-02 (in 2 days)."* Under that: the ticket number, which agent asked (with its emoji), and a reminder that *cash moves only when you approve*.

**Why:**
- **It's the only red on the page.** That makes it impossible to miss, and it signals that this button has real consequences.
- **The amount is on the button itself,** so you always know what you are agreeing to before you click.
- **It never greys out.** If no name has been typed, clicking it highlights the "Approving as" box instead of failing silently. The name is required because the pay tool refuses to pay without a real person on record. The box remembers your name between visits.
- **Deny is plain grey text.** It's available, but it doesn't compete with the main action.
- **The bar doesn't disappear when nothing needs approval.** It turns into a calm green check: "No approvals needed right now." Keeping it in the same spot means you always know where to look.

## How the agents look different

Each agent is a **person emoji in a white circle, with a second emoji badge for their job**:

| Agent | Person | Badge | Why |
|---|---|---|---|
| Boss | 🤵 | 👔 | Suit and tie: the one who makes the final call |
| Inventory | 🧑‍🏭 | 📦 | Warehouse worker with a box: stock and restocks |
| Accounting | 🤓 | 🧮 | Glasses and an abacus (there is no calculator emoji): the numbers person |
| Facilities | 👷 | 🏢 | Hard hat and a building: the shop space and the lease |
| Customer Service | 😊 | 🎧 | Friendly face with a headset: talks to customers |

**Why emoji:** they are instantly readable, need no image files, and give each agent a personality. That makes the delegation easy to follow: "Boss asked Facilities…" is easier to picture than a list of role names. The same emoji appear again in the activity log, the summary, and the approval bar, so you can recognize an agent anywhere on the page. You (🙋) and the board itself (🗂️) get their own emoji in the log too.

**Each agent card shows its state:**

| State | Look | Meaning |
|---|---|---|
| Idle | Pale blue card, no glow | Not part of this run yet. Shows its job description. |
| **Working** | White card with a **pulsing blue glow**. The avatar bobs gently. Blue "Working" label. | This agent is thinking or calling a tool right now. |
| Waiting | Soft blue ring, no pulse. Says "Waiting on Facilities…" | It handed work to a teammate and is waiting for the answer. |
| Done | Green "Done" label | Finished. Shows its last line (for example, Boss's decision). |

**Why separate Working and Waiting:** Boss technically "runs" for the whole ticket, so if every busy agent glowed, Boss would glow nonstop and the glow would mean nothing. Only agents doing the work right now glow. An agent that is waiting gets a quieter ring, so your eye goes to whoever is actually working. Under each name, one line shows the agent's latest action ("Used list_bills_due", "Got a task: …").

## Live activity and "What each agent did"

- **Live activity** turns each step of the audit trail into a readable sentence: "Asked Facilities: handle the rent notice…", "Used list_bills_due", "Requested pay_rent (lease_id 1): needs your approval", "Decided: Resolved…".
  - **Color shows importance.** Tool calls are light blue, decisions green, anything needing you red. Routine items, like tool results and board saves, are plain grey text so they don't crowd the log.
  - **Details are hidden until asked for.** Raw tool output sits behind a small "details" link. The log scrolls to the newest line on its own.
  - **A re-check is labeled.** When the run is the automatic re-check after an approval, the heading says "(re-check after approval)".
- **What each agent did** is the after-the-fact recap. Boss's call is at the top in a colored box (green when resolved, amber when waiting), with the customer draft folded underneath, marked "saved on the board, not sent." Below that, each agent gets one line on what it found, plus pills naming the tools it used.

**Why both:** the live log answers "what is happening right now?" and the recap answers "what happened?" Someone checking in later can read the recap without scrolling through every step.

## How resolved tickets show up

- **Status chips on every ticket:**
  - **Open** (blue)
  - **Agents working** (solid blue with a blinking dot)
  - **Re-check queued**
  - **Waiting on approval** (amber)
  - **Blocked / Needs info** (red)
  - **Resolved** (green)

  Each ticket also has an icon for its type: 👕 order, 🏠 rent, 🏷️ discount.
- **Resolved tickets fade slightly.** The subject turns grey, so finished work steps back and open work stands out.
- **Statuses are honest.** A run that ends with a payment still pending shows **Waiting on approval**, not Resolved. When you approve a ticket's last payment, Boss automatically **re-checks** that ticket. Boss confirms the bill was paid and sets the ticket to **Resolved**. In our test, that re-check used about 2.7k tokens. We chose this over marking tickets resolved automatically, because the board should never say "done" while money is still owed or a restock is still needed.
- **The page follows the work.** When a run starts, the board jumps to that ticket, and the start button changes to "Team is working…" or "Team busy on #102". The backend only allows one run at a time, and the button makes that clear. After a ticket has been run once, the button reads "Run agent team again".

## How cash shows up

- **Location:** a large blue figure in its own card at the top right: **Checking balance $3,400**, with a small line below: "Bills due $3,240 · $160 left if all paid".
- **Change animation:** when the balance changes (after you approve a payment), the card **pulses with a blue glow and grows slightly** for a moment.

**Why:**
- **Always in sight.** Cash is what every approval affects, so it stays where you can see it while you approve.
- **Context with the number.** The "left if all paid" line shows what's coming up, so a $2,400 approval doesn't come as a surprise.
- **Confirmation by animation.** The pulse shows your click had a real effect, without a pop-up.

## Other user-friendly touches

- **Clear empty states.** Before anything runs, each panel explains itself ("No activity yet. Start the agent team to watch them work here.") instead of showing a blank box.
- **A banner when the backend is down.** If the backend isn't running, a red banner says so and gives the exact `uvicorn` command to start it.
- **Short notices after each action:** "Paid. Boss is re-checking ticket #102…", "Denied. Nothing was paid." Each notice disappears after a few seconds.
- **Reset asks first.** **Reset shop** asks for confirmation and is turned off while agents are working, so you can't wipe the database mid-run.
- **Live updates without reloading.** The board checks for updates every 1.5 seconds while agents work and every 5 seconds otherwise. That's fast enough to watch the glow move from agent to agent, and it costs no extra AI tokens because it only reads the backend.
