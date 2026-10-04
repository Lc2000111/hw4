# Campus Customs: Storefront + AI Shopping Assistant (MGT 409, HW4)

A storefront for **Campus Customs** (officially licensed Yale apparel, 57 Broadway, New Haven):

- **Frontend:** React + Vite + TypeScript. Home, Products (filters and sort), product pages, About, Log in, and Create account, plus a chat assistant on every page.
- **Backend:** Python FastAPI. Products, accounts, saved chat history, and a streaming chat API.
- **Agent:** PydanticAI, using `gpt-5.6-luna` through Portkey. It answers shopper questions with **honest prices and stock from the local SQLite database**, puts matching products on the page, remembers logged-in shoppers, and keeps an append-only audit trail.

## Repository layout

```
hw4/
├── README.md              ← you are here
├── ai_prompts.md          every AI prompt used, one section per problem
├── requirements.txt       Python dependencies (backend)
├── .env.example           template for your API key (placeholders only)
├── .gitignore             keeps .env, the database, and product images out of git
├── backend/
│   ├── main.py            FastAPI app (the file uvicorn runs)
│   ├── prompts/prompt.md  ┐
│   ├── agent.py           │  the agent itself: system prompt, wiring (model, limits,
│   ├── tools.py           │  validators, streaming), tools, and Pydantic types
│   ├── models.py          ┘
│   ├── db.py              shared read-only database helpers
│   ├── auth.py            password hashing (PBKDF2) and sessions
│   ├── memory.py          saved chat history for logged-in shoppers
│   ├── safety.py          sensitive-data guard and crisis guard
│   └── audit.py           append-only audit trail → output/audit_trail.json
├── frontend/              React + Vite + TypeScript storefront (src/, index.html, vite.config.ts)
└── output/
    ├── harness.md         ★ how the whole system works (models, tools, safety, specs)
    ├── usability.md       Problem 9 improvements
    ├── design.md          Problem 10 design
    ├── app_check.html     Problem 11 test report (open in a browser) + app_check_images/
    └── audit_trail.json   agent-loop audit trail (append-only)
```

**Not in git: the local-only data pack.** Put it in place before running:

```
hw4/data/campus_customs.db     ← the SQLite database (catalogue, inventory, users, …)
hw4/data/products/*.jpg        ← product images (paths match the catalogue table)
```

If you have the course `data.zip`, unzip it inside `hw4/` (it creates `data/`):
```bash
unzip data.zip
```

## Prerequisites
- Python 3.11+ (developed on 3.14)
- Node.js 20+ and npm (developed on Node 24)
- A Portkey API key with access to `gpt-5.6-luna`

## 1. Set up the API key
```bash
cp .env.example .env
# then edit .env and set PORTKEY_API_KEY=<your key>
```
The backend loads the nearest `.env` (in `hw4/` or a parent folder). Never commit `.env`. Without a key the shop still works (products, accounts), but the chat answers "assistant offline".

## 2. Run the backend (FastAPI + agent), port 8000
From `hw4/`:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd backend
source ../.venv/bin/activate        # Windows: ..\.venv\Scripts\activate
uvicorn main:app --reload --port 8000
```
The backend **must be started from `backend/`** (it uses plain imports such as `import agent`).

On first start it adds a `sessions` table and a `page_results_json` column to `chat_messages` if they're missing (safe to repeat).

Check it: <http://localhost:8000/api/health> should return `{"status":"ok"}`.

## 3. Run the frontend (React + Vite), port 5173
In a second terminal, from `hw4/`:
```bash
cd frontend
npm install
npm run dev
```
Open **<http://localhost:5173>**. Vite forwards `/api` and `/media` to the backend on port 8000, so both must be running.

## 4. Try it
- **Log in** with the seed account `test@campuscustoms.yale.edu` / `password`, or create a new account (password ≥ 8 characters).
- **Chat** (bottom-right "Ask Campus Customs"):
  - *"What hoodies do you have?"* puts all matching hoodies on the page as product cards.
  - On a product page: *"Is this in XL?"* or *"Do you have this in pink?"* gives an honest answer from the live database.
  - *"Is the Baseball Left Chest Crewneck available in XS?"*: "sold out in XS", plus the sizes in stock.
- **Products page:** filter by category or "in stock in [size]", and sort by price.
- **Ask the agent from a terminal** (inside `backend/`): `python agent.py "Do you have navy hoodies in M?"`

## Useful commands
| Command | What it does |
|---|---|
| `npm run build` (in `frontend/`) | Type-check and build the frontend |
| `npm run lint` (in `frontend/`) | Lint with oxlint |
| `python3 -c "import json; print(len(json.load(open('output/audit_trail.json'))))"` | Count audit-trail entries |

## Where to read more
- **`output/harness.md`**: architecture, the flow of one chat turn, every model field and why, tools, safety rules and code guards, loop limits and result caps, the audit trail, and the API reference.
- **`ai_prompts.md`**: the prompts used for each problem.
