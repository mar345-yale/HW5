# Homework 5 — AI Prompts

A running log of every prompt used with the AI assistant while completing Homework 5, grouped by problem, so the work can be reviewed later.

## Setup

1. okay, today we are going to work in the homework 5 folder. for the rest of the day, put all my stuff in there. prove it with a joke.txt
2. before we get too far, lets build a virtual environment for this project. eep the portkey_api_key in the .env from my root and we will use that to call openAI agents later. I will use model gpt-6-luna today
3. Great. now here is the scenario for today's project. I dont need you to take any action, I just want you to know roughly what we are doing.

   Scenario: Campus Customs Multi-Agent Operations is the agentic team that runs the sho. Open tickets land on a board - customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. We will build 3 pieces that talk to each other: an MPC server, a FastAPI backend with a multi-agent team, and a REact dashboard so a human can watch the agents t work and approve requests. The agent team should have full connectivity so that any agent may delegate tasks to any other agent for help In the project, we will build the following agents:
   - Boss: reads each ticket, decides who should work on it, and make final calls.
   - Inventory: checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock.
   - Accounting: watches cash and invoices, checks margins, and preps payments or purchase orders for human approval
   - Facilities: handles the shop space side (leases, rent, etc.)
   - Customer Service: drafts messages for customers

   Shop Rules:
   - The field desk.date_today is "today" for the shop. Use this date to determine what is overdue.
   - Vendor lead times come fromt he vendors table.
   - A vendor will not ship new product while they still ahve an open unpaid invoice.
   - Human approval is required for any payments. If payment is made, make sure to update the relevant table.
   If there is not enough cash, the pay tool must refuse (no negative balances)
   - Cash will only go out in this homework (there is no model revenue in the problem so no money will be coming in)
   - Before a full run to resolve the tickets, make sure to reset the db to the original values.
   - Do NOT email customers or call real vendors. Drafts will stay on the board.
   - This is all pretend for a homework assignment. Never invent data or prices.

   We will use my PORTKEY_API_KEY for AI calls with only gpt-6-luna throught he portkey. Multi-agent chats are expensive and burn tokens too fast.

   We will work one problem at a time together.

## Problem 1: Vibe Coder Prompts

1. perfect. before we continue, I need you to create a markdown file named AI_prompts.md. We will keep this updated as we work. In this mark down, I need you to put 11 sections labeled Problem 1 - 11. In each section, put the problem number and title, and all of my prompts for each problem. This prompt is Problem 1 - Vibe coder prompts

## Problem 2: Study the Campus Customs Database

1. Okay now for Problem 2: Study the Campus Customs database.
2. I pulled in a file under data called campus_customs.db. That file is the original shop database with tables that inlude desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices. 

   Copy the orginal file to data/campus_customs_new.db. 

   The tools we build today will update the copy file. We will point the MPC server and backend at that. Keep campus_customs.db untouched so we can reset when we want to restart resolving the tickts in the future.

   Then study the three open tickets so we can see how they link to other tables.

   After that, start an output/harness.md. For each table, list the fields and one short line on why that table matters for the agents.

## Problem 3: Build the MCP Server

1. okay lets move to Problem 3: Build the MCP server.

   Lets build an MCP server in mcp_server/ using FastMCP. It needs to talk to data/campus_customs_new.db. Every agent will use the tools in this MCP server.

   I want to add only 3 tools for now that will help unlock the tickets when looking at the db. give me a few examples to chose from with clear names.

   Reminder: never invent any data and only use info in the db.
2. lets go with 1, 2, and 5
3. Now in output/harness.md, list each of the 3 mcp tools and for every tool, include the follwing: which table it reads, which ticket it helps unlock, and one sentence on why that tool is the right one for that ticket. 

   After that, add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the 3 tools it has.

## Problem 4: Add the MCP Server to Vibe Coder and Test Each Tool

1. Now for Problem 4: Add the MCP server to vibe coder and test each tool.

   Add the MCP server to this project so the vibe coder can call the tools. Save the connection JSON text in .mcp.json at the project root (or however this vibe coder saves local MCP server lists).
2. i dont know how to do that
3. I'm a bit confused.. I thought I was already in the HW 5 folder with it open and working. Here is a screen shot of my vibe coder folders: [screenshot of the VS Code Explorer]
4. I dont need that MCP server that is currently at the root. Could we just replace it for now?
5. Call each campus-customs MCP tool: list_open_tickets, get_ticket_details for 101, 102, and 103, and list_bills_due. Keep logging my prompts in Homework-5/AI_prompts.md.
6. Sweet. now that we tested each of the 3 tools, save the evidence of our test in output/mcp_smoke.json. 

   For every tool include: the prompt that was asked, the tool name, and the tool output (must match values in data/campus_customs_new.db.

## Problem 5: Build the Agent Team and Grow the MCP Tools

1. Now for Problem 5: Build the agent team and grow the MCP tools.

   Per our scenario setup, build the agentic team for Campus Customs using PydancticAI: the boss, inventory accounting, facilities, and customer service agents. They need prompts, models, and agent loops so they can delegate work to each other with full connectivity. I want these to be efficient and cost effective so we dont burn through tokens.

   I want the agent prompts in backend/prompts/ with one file per agent. Then put data types in backen/models.py, and the agent files under backend/ with a layout that has 5 clear roles. These should be detailed prompts that cover all aspects of an agents work and scope. Remember to use PORTKEY_API_KEY and only gpt-6-luna for every agent. 

   Dont add any tools to the MCP server yet, we will do that next
2. Okay now we can add more tools the agents need tot he MCP server so htey can work on the open tickets. Shop facts will still come from the CMP server over data/campus_customs_new.db. Do NOT invent a second shop-tools layer that bypasses the MCP. Give me a list of tools you think would be best for each agent rated from most important (critical) to least important (would be nice to have). Ill approve each tool
3. Okay lets do all of them but I 100% want to ensure the 2 safeguards are in place for A1 and F1. For C1, lets add a small drafts table.
4. Thats fine for now! Now wire the agents so they append to output_audit_trail.json as they run: for each agent-loop step, recored enought to audit later. Append to this file - do not wipe it each run. 

   Then in output/harness.md, list each agent and each MCP tool (including onces we added in this problem) olong with which table the tool uses. Also add a short safety section: the guardrails a real business would want if agents touch real customers and real money, plus limits that keep token use in check.

   After that, update mcp_server/READMEmd so the tool list matches what we have now.
5. okay. going to pause this project for now and pick back up tomorrow
6. okay we're back at it! go ahead and update the agents to gpt-6-luna please
7. the audit file should stay as is. what are the potential hazards of question 2 again?
8. lets go with option a
9. did you wire the backend yet? If you did not, dont do it yet
10. can you build me a quick html file that shows the current 3 tickets we will be working on?

## Problem 6: Plan the Three Tickets

1. Okay lets move on to Problem 6: Plan the three tickets.

   I drafted a quick word doc write up of what I expect the team of agents to do on each open ticket. I need you to convert that to an html as output/desk_tickets.html which should be a page you can double-click to open. It should have 5 total tabs with my write-up for each ticket as Tab 101, Tab 102, and Tab 103 respectively. I also want an empty tab for cash and an empty tab for reflection which we will add to later. go!
2. the word doc is ticket expectations
3. can you open it for me ?

## Problem 7: Backend Routes

1. that looks perfect. Okay now for Problem 7: Backend routes.

   The React frontend dashboard (which we will get to in the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following:
   - Return the three tickets and whether each is open or resolved.
   - Take a ticket id and run the agent team on that ticket
   - Return recent agent events (what each agent said and which tools they used) so the board can refesh)
   - Aprove a payment or purchase after a human clicks approve (agents only prepare the pay: this route is what actually chages cash)
   - Return the current checking balance from cash_accounts
   - Reset the db to the original values when I want to try a fresh run.

   From the backend/ folder, I should be able to start the server with the command: 
   uvicorn main:app --reload --port 8000
   that should turn on the backend at http://localhost:8000 so the frontend dashboard can call the routes.
2. (Answered questions) Tickets: "Add list_tickets tool (Recommended)". Purchases: "Payments only for now (Recommended)".
3. lets leave it for now but remend me about the waiting_on_approval problem later.
4. okay now in output/harness.md, list each route in one line (what URL / what it does)

## Problem 8: Agent Dashboard

1. Moving on to Problem 8: Agent dashboard.

   Build the frontend dashboard in frontend/ with React + Vite + typeScript. The page should call on the routes we build in problem 7. At a minimum, the board should have the follwoing: 
   - List all 3 tickets
   - Let the user pick one ticket and start the agent team on it.
   - Show each agent and what they are saying/doing while the ticket runs
   - Mark a ticket resolved when the run finishes
   - Show a short summary of what each agent did on that ticket
   - Let a human approve a pay or purchase when asked. (lets make this a glowing red button)
   - Show the checking balance (it should update after an approved pay)

   I want the dashboard to be very user friendly with a clean blue and white design. I dont want harsh edges on the dashboard, and i want all of the agents to look like individual emojis (suit and tie for boss, hardhat for facilies, glasses and calculator for accounting, you get the idea). Make them glow when they are being used. I want the approval required button to be at the top with a clear description next to it of what should be approved. 

   The frontend should talk to the backend at http://localhost:8000. On the backend, allow the vite page origin (usually http://localhost:5173) so the browser is allowed to call the routes.
   The board should start with the command:
   npm run dev
2. (Answered question) Resolved: "Re-check after approval (Recommended)".
3. Great. now write output/design.md with what we chose for the dashboard look (layout, how agents read differenty, how resolved tickets and cash show up) and why (including creative and user friendly choices).
4. i tried to run the backend and got this: [screenshot: `uvicorn main:app --reload --port 8000` run from Homework-5 -> "ERROR: Error loading ASGI app. Could not import module \"main\"."]
5. okay i ran both. now open the frontend page so i can see it!

## Problem 9: Resolve the Tickets

1. Okay now for Problem 9: Resolve the tickets.

   I went to our dashboard and ran the agents against all 3 tickets. Without changing any of my previous inputs, open output/desk_tickets.html from Problem 6 and on each ticket tab, fill in what ACTUALLY happened under my predictions for each run to include which agents worked, what they delegated,, and which tools they used. 

   On the cash tab of that html, itemize the money with the following info:
   - Starting checking balance (after the reset happened)
   - For each ticket, how cash changed when that ticket resolved/finalized and why (which pay/purchase, dollar amount)
   - Ending checking balance (it must match cash_accounts in the working db)

   Also save:
   - output/resolved_tickets.json. For each ticket: id, final status, short outcome, what each agent contributed and any human approvals.
   - output/resolved_board.html. A page you can double-click with a screenshot of the React Board for EACH resolved ticket.

   Then append real runs to output/audit_trail.json.
2. nice! im going to take a break and come back later. does keeping the frontend and backend live use any tokens?
3. okay im back. lets finish this problem by finishing output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules. dont rewrite something if it is already there.

## Problem 10: Reflection

1. Okay now for Problem 10: Reflection.

   I want to make a write up in output/desk_tickets.html and fill the Reflection Tab. I want a clear but appropriately thorough discussion so that a professor can understand the following: 
   - How we evaluate the performance of the agent on each ticket and why? Personally i think we did a good job of styaing safe and not allowing our agent to run out of money in the final ticket. Human intervention is great here.
   - For each ticket, how did my prediction compare to the actual plan? I think i was a bit weak in my analysis and feel free to comment on that when you answer.
   - What would have been simpler as one agent with tools and why?
   - Describe 3 new problems Campus Customs might face that this agent team could solve with the tools we built.
   - Describe 3 new problems Campus Customs might face that this agent team could NOT solve with the tools we built, and then explain the tools the agents would need to solve them.

   When answering, remember to tie all discussion to the app we just built and consider the tickets we ran. Use the ticket tabs and cash tab on the same page as our evidence.

## Problem 11: Submit to GitHub

1. Okay now for Problem 11: Sibmit to GitHub.

   I want to create an additional file named hw5 that has all of our data ordered like this picture. [screenshot: hw5/ tree with AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, README.md, data/ (campus_customs.db, campus_customs_new.db), mcp_server/ (server.py, README.md), frontend/, backend/ (main.py, models.py, prompts/ boss.md, inventory.md, accounting.md, facilities.md, customer_service.md), output/ (harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json, resolved_board.html, audit_trail.json, github_url.txt)]

   Since im going to push this to a public GitHub (not just yet), remember i never want to push my real .env to a public repo, so include .env.example with placeholders only if necessary.
2. The README should explain: copy origianl db to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full 3-ticket run. If it doesnt, feel free to update that!
