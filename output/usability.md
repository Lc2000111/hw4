# Campus Customs: Usability Improvements (Problem 9)

Four improvements: two on the **agent/backend** (speed first, as requested, then safety) and two on the **front end**. Each section covers **what was added**, **why it helps a Campus Customs shopper or the business**, and **where to see it** in the running app (backend on :8000, `npm run dev` on :5173).

| # | Type | Improvement | Where to see it |
|---|---|---|---|
| A1 | Agent / backend | **Faster answers**: product-page preload, slimmer tool results, parallel lookups, live progress streaming | Open any product page → chat → "Is this in M?" |
| A2 | Agent / backend | **Sensitive-data guard**: card numbers, SSNs, CVVs, and passwords are removed before the AI, the database, or logs see them | Type a card number into the chat |
| F1 | Front end | **Products page filters & sorting**: category chips with counts, "in stock in my size", price sort, shareable URLs | `/products` |
| F2 | Front end | **Quick-question chips + "Ask about this item"** | The chat panel on any page; the pink box on any product page |

---

## A1. Faster agent answers (speed)

### What I added
I first **measured** the agent with a benchmark script: real model calls through Portkey, a unique message each time so Portkey's response cache couldn't hide the true cost, and 5 runs per question. The baseline was **≈3.7 s per answer, always 2 model round trips, ~7–8k input tokens**. Each round trip costs about 1.5 s, so the goal was **fewer round trips** and **instant feedback**.

1. **Product-page preload (fewer round trips).** When the shopper is on a product page, the `page_context` dynamic instruction now reads that product's **live price and per-size stock** from the database and puts it into the agent's context (*"LIVE from the database right now: price $68.00; stock by size: XS 15, S 5 (only 5 left)…"*). It also records those numbers in the `FactLog`, so the Problem 6 fact check still accepts them. The prompt and the `check_stock` tool description tell the agent to answer about "this" item directly, without calling a tool.
2. **Live progress streaming (instant feedback).** A new endpoint, `POST /api/chat/stream`, sends **Server-Sent Events**. It sends "Thinking…" immediately, then a plain-English line for each tool the agent calls: *"Searching the catalogue for navy hoodie…"*, *"Checking stock for basic hoodie big yale in XL…"*, *"Looking through your past chats…"*. The result comes last. It uses PydanticAI's `agent.iter()` to watch each step. The chat widget shows these lines next to a spinner instead of a silent "Typing…". `/api/chat` and `/api/chat/stream` share one code path, so they behave the same.
3. **Slimmer search results.** `search_products` now returns a one-sentence `short_description` (≤110 chars) instead of the full paragraph for each of its 8 results. `get_product_info` still gives the full text. Fewer tokens per tool result means faster and cheaper model calls.
4. **Parallel lookups.** The prompt tells the agent to request several lookups **together in one step** (e.g. two products) instead of one after another.
5. **Kept the prompt cache-friendly.** The long static prompt stays first, and the per-message sections (customer, page, safety) come last. The provider then serves **~93% of input tokens from its prompt cache** (measured: 6,657 of 7,162 tokens cached), which makes calls cheaper and faster.

### Measured result (5 runs each, no response cache)
| Question | Before | After |
|---|---|---|
| Product page: "Is this in XL?" | 3.2 s · 2 model calls · 7,174 input tokens | **2.6 s · 1.2 calls · 4,532 tokens (−37%)** |
| Time until the shopper sees any progress | Only "Typing…" until the full answer (≈3–4 s) | **"Thinking…" in 0.05 s**; the tool status line appears as soon as the model picks a tool |
| Browse: "What hoodies do you have?" | 3.7 s · 2 calls | 3.4 s · 2 calls (a search is genuinely needed) |

In the browser, on the Fencing hoodie page, "Is this in M?" answered in one model call with no tool step ("Yes… in stock in M").

### Why it helps
- **Shoppers:** questions about the item they're looking at, the most common kind of question, now come back faster. When a search is needed, they see what's happening ("Checking stock for … in XL…") instead of a frozen chat, so the wait feels shorter and they're less likely to give up.
- **The business:** fewer model calls and tokens per question mean **lower AI cost per conversation**, especially at peak times like move-in weekend or The Game. The answers stay just as honest, because the preloaded numbers come straight from the database and still pass the fact check.

---

## A2. Sensitive-data guard (safety)

### What I added
A new module, `backend/safety.py`, with `redact()`. **Every** chat message goes through it in `main.prepare_chat` *before* the AI model, the `chat_messages` table, or any log sees it. That includes guest history sent by the browser.

| Data | How it's detected | Replaced with |
|---|---|---|
| Card numbers | 13–19 digits (spaces or dashes allowed) **that pass the Luhn checksum**, so order numbers and phone numbers aren't touched | `[card number removed]` |
| Social Security numbers | `123-45-6789` pattern | `[SSN removed]` |
| CVV / security codes | "cvv 123", "security code: 1234" | `[security code removed]` |
| Passwords | "password is …", "pw: …", but **not** "password reset" or "forgot my password" | `[password removed]` |

- The response tells the widget what happened (`message` = the cleaned text, `redactions` = `["card number", …]`). The shopper's own chat bubble is **replaced by the cleaned text**, and a notice appears: *"For your safety we removed the card number and password from your message. Please never share payment details or passwords in chat."*
- A new `safety_context` dynamic instruction tells the agent what was removed, so it reminds the shopper not to share it and explains that we can't take payments in chat. Then it still answers the actual question.

### Verified
- **Browser:** "My card is 4111 1111 1111 1111 and my password is …" → the bubble shows `[card number removed]` and `[password removed]` plus the notice. The raw number appears nowhere on the page, and the agent replied with a safety reminder plus how to order.
- **Database:** a logged-in test with an SSN and a card number → stored as `my ssn is [SSN removed] and card [card number removed], is the boola boola tee in M?`. A search of `chat_messages` for the raw values finds **0 rows**.
- **No false alarms:** prices, phone numbers, a 13-digit order number, and "how do I do a password reset?" are all left unchanged.

### Why it helps
- **Shoppers:** a mistake (pasting a card number into the wrong box) can't leak to the AI provider or sit in our database, and they're told right away how to stay safe.
- **The business:** storing card numbers would put Campus Customs in scope for **PCI-DSS** compliance and create a data-breach liability. The guard keeps payment data, SSNs, and passwords out of our database and out of third-party AI logs. It's a code-level control, so it works even if the model ignores instructions.

---

## F1. Products page filters & sorting

### What I added
The Products page used to be one long grid of 102 items with a text box. It now has:
- **Category chips with counts:** All 102 · Hoodies 27 · Crewnecks & sweatshirts 29 · T-shirts 25 · Quarter-zips 11 · Jackets 8 · Long sleeve 2. They use a new `category` field on every `ProductCard`, computed by the backend's `db.category_of()` (the same mapping the agent uses), which merges the catalogue's 22 inconsistent garment spellings.
- **"In stock in [size]"** dropdown: only items that actually have that size right now. The chosen size is **highlighted on every card's size pills**, and sold-out sizes are struck through.
- **Sort:** Name, Price low→high, Price high→low, Most in stock.
- **"Showing 21 of 102 items · in stock in M"**, a **Clear filters** button, and a friendly empty state.
- **Shareable URLs:** filters live in the address bar (`/products?category=hoodie&size=M&sort=price-desc`), so a view can be bookmarked or texted to a friend, and the browser **Back** button undoes the last filter.

### Verified
Hoodies + size M + price high→low → "Showing 21 of 102 items · in stock in M" (the database confirms **21** hoodies with M in stock). Every card has M available, prices are in descending order, the URL updates, and Back returns to `?category=hoodie&size=M`.

### Why it helps
- **Shoppers:** "show me hoodies I can actually buy in my size, cheapest first" takes three clicks instead of scrolling past 102 items and opening each product to check sizes. Shoppers who don't want to chat can still browse efficiently.
- **The business:** shoppers spend less time hitting sold-out sizes, which means fewer abandoned visits. Shareable filtered links also work for marketing ("all our quarter-zips": `/products?category=quarter-zip`).

---

## F2. Quick-question chips + "Ask about this item"

### What I added
- **Quick-question chips** in a row above the chat input, which **change with the page**:
  - On a product page: *Is this in M? · What colors does it come in? · How many are left in L? · Show me similar items*
  - Elsewhere: *What hoodies do you have? · Anything under $50? · Show me bulldog designs · Navy crewnecks in M?*, plus *What did you show me last time?* for logged-in shoppers
  - One tap sends the question. Chips hide while the assistant is answering.
- **"Ask about this item"** box on every product page (*"Questions about this item? Our assistant knows its live stock…"*). It opens the chat, already focused on that product through the page context, with the product chips ready.

### Verified
On the Fencing hoodie page, "Ask about this item" opened the chat with the 4 product chips. Tapping "Is this in M?" gave a correct answer ("Yes… in stock in M"; the database has 15). Tapping "Show me similar items" showed live progress, then put 27 similar hoodies on the page.

### Why it helps
- **Shoppers:** many people don't know what a shop chatbot can do, or don't want to type on a phone. The chips show the most useful questions and answer them in one tap, and the product-page button makes the assistant easy to find right where size and color questions come up.
- **The business:** more shoppers actually use the assistant that Problems 5–8 built. And the chips steer people toward questions it answers best and fastest (questions about the viewed item use the A1 preload: one model call).

---

## Files changed
| Improvement | Backend | Frontend |
|---|---|---|
| A1 Speed | `agent.py` (`page_context` preload, `chat_stream`, `describe_tool_call`, `build_response`), `main.py` (`/api/chat/stream`, shared `prepare_chat` / `finish_chat`), `tools.py` (`short_text`, `check_stock` description), `models.py` (`ProductInfo.short_description`), `prompts/prompt.md` | `api.ts` (`streamChatMessage`), `ChatWidget.tsx` (status line + spinner) |
| A2 Safety | `safety.py` (new), `main.py`, `agent.py` (`safety_context`), `models.py` (`ShopDeps.redactions`, `ChatResponse.message` / `redactions`) | `ChatWidget.tsx` (cleaned bubble + notice) |
| F1 Filters | `db.py` (`category_of`, `category` on products), `models.py` (`ProductCard.category`) | `pages/Products.tsx`, `ProductCard.tsx` (size highlight), `index.css` |
| F2 Chips | — | `ChatWidget.tsx` (`quickQuestions`, `OPEN_CHAT_EVENT`), `pages/ProductDetail.tsx` (Ask box), `index.css` |
