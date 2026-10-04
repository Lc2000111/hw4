# AI Prompts — MGT 409 Homework 4

This file logs the AI prompts used for each problem in this assignment. It is updated as the work goes on.

---

## Problem 1: Vibe coder prompts

### Prompt 1
> i am going to complete a homework problem set. Put one section for each problem. and each section must include the problem number and title. So let's begin, Problem 1: Vibe coder prompts. Create AI_prompts.md at the start of this assignment and then updated as i work.

**Result:** Created `AI_prompts.md` and set it up with one section per problem.

---

## Problem 2: Understand the database and start the harness

### Prompt 1
> Problem 2: Problem 2. unzip the zip file in the hw4 folder. There you will have data/campus_customs.db, which is a SQLite database with tables catalogue, inventory, and users (one test user is already there). You will also have data/products/, which are product images; paths mathc the catalogue table. In Problem 2, look at the database data/campus_customs.db and understand the fileds of each table. You should understand catalogue, inventory, and users. Throughout all the problems, i am going to build a reach + vite typescript front end and a python fastapi backend whose brain is the pydanticai agent. The end product is a real customer website with a helpful chatbot for Campus Customs. Shoppers should be able to browse products, create an account, chat about merch, see matching items appear on the page, and get honest answers about price and stock from a local database. I am going to give you detailed instruction for each problem so don't rush. Use my portkey_api_key or maybe just the API key that Claude uses. Start the file output/harness.md. Write down each table and its fields, and one short line on why each field matters for the shop or the chatbot. I will keep growing this harness file in later problems (models, tools, safety, specs).

**Result:** Unzipped `data.zip` into `data/` (the database plus 102 product images). Checked the schema, sample rows, and data integrity with `sqlite3`. Created `output/harness.md` with every table, its fields, and one line per field on why it matters.

---

## Problem 3: Build the Campus Customs website

### Prompt 1
> Problem 3: Build the Campus Customs website. Scaffold a React + vite + typeScript front end for Campus Customs. Put a nav bar at the top that links to the main pages: Home, Products, About Us, Log in, Create account. Pull Campus Customs-style wording from yalebulldogblue.com for Home and About Us, but write these pages in my own voice (don't copy the original site text). On the Products page, show product images from the catalogue (use the image paths in the database) with basic product info (name, price, short description). Make each product open a single-item page (large image on one side, full product text on the other - description, price, sizes/stock when you have them). Clicking a card on Products should take the shopper there. Add a chat interface in the bottom right of the site (a floating chat panel is fine). It does not need to talk to an agent yet - a stub that will call your backend later is enough for this problem. You will need a small API soon to read the database. It is fine to start a simple fastapi app in backend/main.py just to serve products and images, then grow it into the agent backend in Problem 5.

**Result:** Built `backend/main.py` (FastAPI: `/api/products`, `/api/products/{id}` with per-size stock, a stub `/api/chat`, and images under `/media/products`) and scaffolded `frontend/` (React + Vite + TypeScript, react-router) with Home, Products, product detail, About Us, Log in, Create account, and a floating chat panel. Home and About copy was written fresh, using only facts and tone from yalebulldogblue.com (Campus Customs, 57 Broadway, officially licensed Yale apparel). Checked in the browser: all 102 products load with images, clicking a card opens the detail page with correct stock, and the chat stub reaches the backend. Added section 2 (App skeleton) to `output/harness.md`.

---

## Problem 4: Create account and login

### Prompt 1
> Problem 4: Create account and login. Build a normal create-account / login flow. 1. Create account: first name, last name, email, password (confirm password need to have at least 8 characters) 2. Log in: email and password. New accounts go into the users table. Make sure to store passwords securely so hackers (human or AI) cannot access them. The seed database already has a test user you can use while building: email is test@campuscustoms.yale.edu, password is password. Confirm you can log in as that user, and then a brand-new account you create also works. Update output/harness.md with how auth works (what you store for a user and how passwords are protected.)

**Result:** Added `backend/auth.py` and the `/api/auth/signup`, `/login`, `/logout`, `/me` routes. Passwords are hashed with PBKDF2-SHA256 at 600,000 iterations with a per-user salt, and sessions use an HttpOnly cookie with only a hashed token stored in a new `sessions` table. Also added a lockout after 5 failed logins and identical error messages for wrong password and unknown email. The seed hashes (120,000 iterations) still verify and are upgraded on login. Wired up the Log in / Create account pages and nav bar ("Hi, name" + Log out) in React. Verified in the browser: the seed test user logs in, and a brand-new account can sign up, log out, and log back in. Documented auth in `output/harness.md` §3; test logins are in `TEST_ACCOUNTS.md`.

---

## Problem 5: PydanticAI agent backend

### Prompt 1
> Problem 5: PydanticAI agent backend. Build the shop chatbot as a PydanticAI agent behind FastAPI, plugged into my front-end chat widget. Put the API app in backend/main.py - that is the file you run with Uvicorn. Keep the agent as these four files next to it (same idea as Hw3): 1. backend/prompts/prompt.md - system promot (grow this same file later), 2. backend/agent.py - agent entry/wiring, 3. backend/tools.py - tools the agent can call, 4. backend/models.py - Pydantic/PydanticAI structured types. In main.py, expose a chat route so a message from the website returns a reply from the agent (and wharever else you need for products/auth). You will need the AI model API key for the agent. Put Campus Customs voice and safety basics into prompts/prompt.md (you will expand tools and safety later). Start or update types in models.py for chat replies / product cards as needed. In output/harness.md, note how the front end talks to Fastapi and how the agent is loaded (prompt file + model). Make sure the backend runs from the backend/ folder like this: uvicorn main:app --reload --port 8000

**Result:** Built the shop chatbot as a PydanticAI agent. The four agent files are `backend/prompts/prompt.md` (voice, honesty rules, safety basics), `backend/agent.py` (Portkey `gpt-5.6-luna` model, prompt loading, per-shopper context, `chat()`), `backend/tools.py` (`search_products`, `get_product_details`, `shop_overview`, read-only), and `backend/models.py` (product cards, tool results, `ShopReply`, chat request/response). Added `backend/db.py` for shared database access. `POST /api/chat` in `main.py` runs the agent and returns the reply plus product cards built from the database. Switched to plain imports so the backend runs from `backend/` with `uvicorn main:app --reload --port 8000`. The chat widget now sends recent history and the product being viewed. Tested with the live model (stock, pink, sold-out sizes, follow-ups, prompt injection, off-topic, card numbers) and fixed three search bugs found along the way. Documented in `output/harness.md` §4.

---

## Problem 6: Tools: product info and stock

### Prompt 1
> Problem 6: Tools: product info and stock. Give the agent tools that look up real information from campus_customs.db: product description, price, how many are in stock (by size when the customer asks). The agent must use the database - it should not invent prices or quantities. If a size is out of stock, say so clearly. Expand prompts/prompt.md so the agent knows to call these tools for price and stock questions. Add or update return types in models.py. In output/harness.md, list each tool and explain which model fields you chose for lookup results and why.

**Result:** Replaced `get_product_details` with two dedicated database tools. `get_product_info` returns `ProductDetails` (description, price, colors, availability summary). `check_stock` returns `StockReport` (per-size quantity plus an `in_stock` / `low_stock` / `sold_out` / `not_offered` status computed in code, and a plain-English summary). Both accept product names or ids and understand size words like "medium" or "2XL". Added a fact-check: tools log every price, quantity, and id they return, and an output validator rejects any reply quoting a `$` price or "N left" that no tool returned this turn. Cards are only built for products a tool returned. Expanded `prompts/prompt.md` with a question → tool table and exact wording for sold-out, low-stock, and not-offered sizes. Verified with the live model (9 price and stock questions, all matching the database, including a forged-history test) and with a scripted model that proves the validator catches invented numbers. Documented each tool and the reasoning behind every result field in `output/harness.md` §5.

---

## Problem 7: Chat search that updates the page

### Prompt 1
> Problem 7: Chat search that updates the page. Now we will add a neat feature to the site. When a customer asks about a type of item - for example "what hoodies do you have?" - the agent should search the catalogue and the website should dynamically show those matching items as product cards (image, name, price, short info). This is an API contract: the agent returns structured product matches and then the front end renders them on the website. After the dynamic product cards are loaded by your new feature, make sure the same single-item page behavior you built in Problem 3 still works: each product card - including the ones the chat just put on the page - should still open that detail view (large image + full info) when clicked. Update prompts/prompt.md and output/harness.md so it is clear how search results reach the page.

**Result:** Added a chat → page API contract. `search_products` now returns a `search_id` and saves all of its matches. The agent's `ShopReply` gained `show_on_page: {search_id, title}`. The backend turns that into `ChatResponse.page_results`, with every match rebuilt as a `ProductCard` from the database. In React, a `ChatResultsProvider` context plus a `ChatResultsPanel` at the top of every page render those matches with the same `ProductCard` component as the Products grid, so every card still opens the single-item page. The panel folds into a bar when you navigate, so the product page is visible right away, and the chat bubble gets a "View N on the page" button. Also added size pills to cards, scroll-to-top on route change, and a "best-matching tier" fix to search (bulldog crewnecks went from 29 loose matches to 5 real ones). Updated `prompts/prompt.md` ("Showing products": page vs chat channels) and `output/harness.md` §6. Verified the full flow in the browser, desktop and mobile.

---

## Problem 8: Customer memory

### Prompt 1
> Problem 8: Customer memory. When a shopper is logged in, save their chat history in the database in an appropriate table and relaod it when they return. The agent should know who is chatting (name, email) - put that in agent deps (or an equivalent clear pattern) and/or tools the agent can call. Also pass enough page context that if someone is on a product page and asks "do you have this in pink?", the agent knows which item they mean. Hint: you can put code into the agent context. Guests can still chat, but history only needs to persist for logged-in users. Document in output/harness.md: how user chat history is stored, what customer fields the agent sees, and how page context is passed.

**Result:** Logged-in chats are now saved in the existing `chat_messages` table (new `page_results_json` column plus an index) through a new `backend/memory.py`. For logged-in shoppers the agent's history comes from the database, never from the browser, and each turn is saved. Added `GET` and `DELETE /api/chat/history`; cards are rebuilt from the current catalogue on reload. The agent knows who's chatting through `ShopDeps.customer` (`CustomerProfile`: first and last name, email, member-since date), a `customer_context` dynamic instruction, and two new tools (`get_my_account`, `recall_previous_products`) that only ever read the current shopper's own data. Page context: the widget sends `PageContext` (path, page type, product id, current results title), and a `page_context` dynamic instruction looks the product up in the database so "this" resolves to the right item with its real colors. Frontend: saved chat reloads on login, resets on logout, and has "Saved conversation" dividers, a "Clear history" button, and a guest or saved status line. Verified in the browser and over the API (pink on a product page, reload persistence, logout reset, a new session remembering, forged history ignored, privacy refusal). Documented in `output/harness.md` §7.

---

## Problem 9: Usability improvements

### Prompt 1
> Problem 9: Usability improvements. Now that the core shop works, improve it. Choose and implement: 2 front-end usability improvements and 2 agent/backend usability improvements. Front-end improvements are things that make the site look better and make it easier to use. Agent/backend improvements are things that make the agent output better, more accurate, or safer. These could be new agent tools or things that make the agent run faster or cheaper. Write output/usability.md before or as you build. For each of the improvements, says: What you added, and Why it helps a Campus Customs shopper or the business. Then make sure all improvements actually show up in the running app. Graders will read the write-up and look for the features. For the improvements, I want to improve speed and others are your freedom to choose.

**Result:** Wrote `output/usability.md` and built four improvements, all checked in the running app.
- **A1 Speed:** benchmarked first (≈3.7 s, 2 model calls per answer, with Portkey's response cache bypassed). Then preloaded live price and stock for the product being viewed into the agent's context (product-page questions: 2 → 1.2 model calls, −37% tokens, 3.2 s → 2.6 s), added `/api/chat/stream` (Server-Sent Events) with live progress in the chat ("Checking stock for … in XL…" after "Thinking…" in 0.05 s), shortened search results, asked for parallel lookups, and kept the ~93% prompt-cache hit rate.
- **A2 Safety:** `safety.py` removes card numbers (Luhn-checked), SSNs, CVVs, and passwords before the AI, the database, or logs see them; the shopper sees the cleaned bubble plus a notice; 0 raw values were found in the database.
- **F1:** Products page category chips with counts, an in-stock-in-size filter, sorting, Clear filters, and shareable URL filters (verified 21 hoodies in stock in M, matching the database).
- **F2:** page-aware quick-question chips in the chat, plus an "Ask about this item" box on product pages.

---

## Problem 10: Style the website

### Prompt 1
> Problem 10: Style the website. Add creative design so the site feels like a real Campus Customs storefront - fonts, color, hierarchy, motion, product presentation, chat feel. You will get more points for imaginative and innovative design. Write output/design.md: what you changed and why it should help customers stick around and buy. Keep it concrete and short.

**Result:** Restyled the whole site as a "Varsity Night" storefront: black and hot pink with collegiate details.
- **Type and texture:** fonts are Graduate (varsity), Bricolage Grotesque, and Inter; added a film-grain texture; one pink accent, with amber only for scarcity.
- **Brand mark:** an SVG chenille "CC" patch serves as the logo, chat avatar, and chat launcher.
- **Home:** a pink scoreboard ticker (true facts only); an outlined neon "BULLDOG" hero with floating polaroid products carrying paper hang-tag prices; a shop-by-category rail; a "Going fast" rail based on real stock (≤30 units) with stock meters.
- **Product cards:** hang-tag prices, a cursor-following 3D tilt, staggered entrance, and an honest "Going fast" / "Only N left in M" badge.
- **Product page:** breadcrumb, cursor zoom, color swatches, ticket-stub size tiles, a trust row, and "You may also like".
- **Chat:** patch avatar, spring-open panel, bouncing typing dots with live status, and message pop-in.
- **Site-wide:** page transitions, a pennant footer, and reduced-motion support.

Checked desktop and mobile in the browser (no horizontal overflow). Wrote `output/design.md`.

---

## Problem 11: Site testing (app check)

### Prompt 1
> Problem 11: Site testing (app check). Test the live site and document it in output/app_check.html (a page you can double-click open). Include clear screenshots and short captions for: 1. Chat checking the inventory level of an item (honest stock/price from the DB) 2. The dynamic search-result cards appearing after a category question (e.g. hoodies) 3. One of the usability features you added in Problem 9. Make the HTML easy to grade: heading for each check, screenshot, one or two sentences on what the screenshot proves. Put the screenshot image files in output/app_check_images/ and link them from app_check.html with relative paths (for example app_check_images/inventory.png).

**Result:** Tested the live site in the browser as a guest and wrote `output/app_check.html` with 9 screenshots in `output/app_check_images/`, linked by relative paths.
- **Check 1, inventory:** the chat says "$68.00, only 2 left in XL" on a product page; the page's own tiles agree; and "Baseball… sold out in XS" is handled correctly. All numbers were verified against `campus_customs.db`.
- **Check 2, dynamic cards:** "What hoodies do you have?" puts 27 product cards on the page, and a chat-loaded card opens the full detail page.
- **Check 3, Problem 9 usability:** Products filters (21 hoodies in stock in M, matching the database), plus live progress streaming and the card-number guard (0 raw numbers stored).

Testing found and fixed two issues:
- **Price tags:** the hang-tag text was pink with a varsity "6" that read like "8"; it now uses a bold display font with even-width digits, in dark ink.
- **Checkout wording:** the agent mentioned a "checkout" that doesn't exist; the prompt now says the site has no cart and buying happens at 57 Broadway.

---

## Problem 12: Audit trail, safety, finish harness

### Prompt 1
> Problem 12: Audit trail, safety, finish harness. Keep an append-only output/audit_trail_json of agent-loop activity (time, tool name, short args/result, stop reason). Do not wipe it between runs. Also, think of some safety rules to give the agent and put them in prompts/prompt.md. Finish output/harness.md so it is clear how the system works. Model fields in models.py and why you chose them, tools and abilities, safety rules, specs (loop limits, result caps, models, how to run front + back)

**Result:**
- **Audit trail:** added an append-only `output/audit_trail.json` (`backend/audit.py`, `AuditEntry` models): one entry per agent-loop iteration with UTC time, model, tool calls (shortened args), one-line results (including `ModelRetry`s and fact-check rejections), tokens, stop reason (`continue` / `final_output` / `usage_limit` / `content_filter` / `safety_guard` / `error`), and turn time. New entries are appended before the closing `]`, so the file stays valid JSON and is never wiped; a write from a separate process kept every earlier entry. It logs no names, emails, or card numbers.
- **Audit-driven fix:** the audit showed a "Boola Boola Tee" question taking 4 iterations, so name lookup now handles garment synonyms and near-exact names (now 2 iterations).
- **Safety rules:** wrote 6 groups of rules in `prompts/prompt.md` (honesty; money/orders; sensitive data and privacy; prompt injection; respect and wellbeing; scope). Testing found that a crisis message was blocked by the provider filter and got a salesy refusal, so I added a code-level crisis guard (`safety.is_crisis`) that replies with care and 988 before any model call. Eight adversarial tests pass.
- **Harness:** rewrote `output/harness.md` as the complete reference: architecture and turn flow, specs (run front and back, models, every loop limit and result cap), database fields, every `models.py` field and why, tools and abilities, safety rules and code guards, audit trail, memory and page context, the chat → page contract, API and frontend map, and a verification log.

---

## Problem 13: Push to GitHub and submit the URL

### Prompt 1
> Problem 13: Push to GitHub and submit the URL. Put your code in a folder named hw4 and push it to a public GitHub repository. Give me the repo URL. (the link graders can open and close). Do not put your real .env, campus_customs.db, or product images in the github repo. Use .gitignore. Include .env.example with placeholders only. Expected file layout: hw4/ai_prompts.md, requirements.txt, .env.example, .gitignore, README.md, frontend/, backend/, output/. Local-only data pack (not in git): data/campus_customs.db, products/. The agent itself is four files under backend/: prompts/prompt.md, agent.py, tools.py, and models.py. README.md should explain how to run the front end and backend after placing the data pack.

**Result (preparation):** Renamed the prompt log to `ai_prompts.md`, added a root `requirements.txt` (`backend/requirements.txt` now points to it), a full `.gitignore` (excludes `.env`, `data/`, `data.zip`, `*.db`, `.venv`, `node_modules`, `TEST_ACCOUNTS.md`, `.claude/`), and a `README.md` explaining how to place the data pack and run the backend and frontend. Ran `git init`, then scanned the staged files: the real Portkey key, test passwords, database, product images, and raw card numbers are all absent. Committed (63 files).

### Prompt 2
> This is my repository: https://github.com/Lc2000111/hw4. This is my token: [token removed: it was not used, and the user was advised to revoke it]

**Result:** Added the remote `origin` → `https://github.com/Lc2000111/hw4.git`. The assistant did not use the pasted token. The push was run in the user's own terminal, where the user entered their GitHub credentials themselves.

