"""Campus Customs backend (FastAPI).

Problem 3: products API + product images from data/campus_customs.db.
Problem 4: create-account / log-in / log-out with hashed passwords and
           HttpOnly session cookies (see auth.py).
Problem 5: POST /api/chat runs the PydanticAI shop assistant (agent.py).
Problem 8: logged-in chat history is saved and reloaded (memory.py), and the
           agent knows who is chatting and which page they're on.
Problem 9: POST /api/chat/stream sends live progress events; every message goes
           through the sensitive-data guard (safety.py) first.

Run from the backend/ folder (with the hw4 virtual environment active):
    uvicorn main:app --reload --port 8000
"""

import json
import logging
import sqlite3
from contextlib import asynccontextmanager

from fastapi import Cookie, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pydantic_ai import UsageLimitExceeded

import agent
import auth
import db
import memory
import safety
from models import ChatHistory, ChatRequest, ChatResponse, ChatTurn, CustomerProfile, ProductCard, ShopDeps

log = logging.getLogger("campus_customs")


@asynccontextmanager
async def lifespan(_: FastAPI):
    with db.connect_rw() as conn:
        auth.ensure_sessions_table(conn)
        memory.ensure_schema(conn)
    yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only the image folder is public — never mount data/ itself, or the .db file
# would be downloadable.
app.mount("/media/products", StaticFiles(directory=db.PRODUCTS_DIR), name="products")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# ---------- products ----------

@app.get("/api/products")
def list_products() -> list[ProductCard]:
    """All products with basic info and stock, for the Products grid."""
    with db.connect() as conn:
        return [ProductCard.model_validate(p) for p in db.all_products(conn)]


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> ProductCard:
    """One product with per-size stock, for the single-item page."""
    with db.connect() as conn:
        product = db.get_product(conn, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductCard.model_validate(product)


# ---------- accounts ----------

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def public_user(row: sqlite3.Row) -> dict:
    """The only user fields ever sent to the browser — never password_hash."""
    first = row["first_name"] or row["name"].split(" ")[0]
    last = row["last_name"] or " ".join(row["name"].split(" ")[1:])
    return {"id": row["id"], "first_name": first, "last_name": last, "email": row["email"]}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,   # page JavaScript can't read it, so XSS can't steal it
        samesite="lax",  # not sent on cross-site POSTs (CSRF protection)
        secure=False,    # set True when served over HTTPS in production
        path="/",
    )


@app.post("/api/auth/signup", status_code=201)
def signup(req: SignupRequest, response: Response) -> dict:
    email = auth.normalize_email(req.email)
    error = auth.validate_signup(req.first_name, req.last_name, email, req.password, req.confirm_password)
    if error:
        raise HTTPException(status_code=400, detail=error)

    first, last = req.first_name.strip(), req.last_name.strip()
    with db.connect_rw() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with that email already exists.")
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (f"{first} {last}", email, auth.hash_password(req.password), first, last),
        )
        token = auth.create_session(conn, cur.lastrowid)
        user = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    set_session_cookie(response, token)
    return public_user(user)


@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request, response: Response) -> dict:
    email = auth.normalize_email(req.email)
    client = request.client.host if request.client else "unknown"
    limit_key = f"{client}|{email}"
    if auth.is_locked_out(limit_key):
        raise HTTPException(status_code=429, detail="Too many failed attempts. Please try again in 15 minutes.")

    with db.connect_rw() as conn:
        user = conn.execute("SELECT * FROM users WHERE lower(email) = ?", (email,)).fetchone()
        stored = user["password_hash"] if user else auth.DUMMY_HASH
        password_ok = len(req.password) <= auth.MAX_PASSWORD_LENGTH and auth.verify_password(req.password, stored)
        if not user or not password_ok:
            auth.record_failure(limit_key)
            # Same message either way, so attackers can't tell which emails exist.
            raise HTTPException(status_code=401, detail="Incorrect email or password.")

        auth.clear_failures(limit_key)
        if auth.needs_rehash(stored):
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (auth.hash_password(req.password), user["id"]),
            )
        token = auth.create_session(conn, user["id"])
    set_session_cookie(response, token)
    return public_user(user)


@app.post("/api/auth/logout")
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> dict:
    with db.connect_rw() as conn:
        auth.delete_session(conn, cc_session)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"ok": True}


def current_user(cc_session: str | None) -> sqlite3.Row | None:
    with db.connect_rw() as conn:
        user_id = auth.user_id_for_session(conn, cc_session)
        if user_id is None:
            return None
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


@app.get("/api/auth/me")
def me(cc_session: str | None = Cookie(default=None)) -> dict:
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return public_user(user)


# ---------- chat (PydanticAI agent) ----------

def customer_profile(user: sqlite3.Row) -> CustomerProfile:
    """The customer fields the agent may see. Built here, from the session's user row."""
    u = public_user(user)
    return CustomerProfile(
        first_name=u["first_name"],
        last_name=u["last_name"],
        email=u["email"],
        member_since=(user["created_at"] or "")[:10],
    )


def prepare_chat(req: ChatRequest, cc_session: str | None) -> tuple[sqlite3.Row | None, str, list[ChatTurn], ShopDeps]:
    """Shared setup for /api/chat and /api/chat/stream.

    - Sensitive-data guard: card numbers, SSNs, passwords are removed before the
      model, the database, or any log sees the message.
    - Logged in: history comes from the database (not the browser). Guest: from the browser."""
    user = current_user(cc_session)
    message, redactions = safety.redact(req.message.strip())
    if user:
        history = memory.recent_turns(user["id"], agent.MAX_HISTORY_TURNS)
    else:
        history = [ChatTurn(role=t.role, content=safety.redact(t.content)[0]) for t in req.history]
    deps = ShopDeps(
        customer_id=user["id"] if user else None,
        customer=customer_profile(user) if user else None,
        page=req.page,
        redactions=redactions,
    )
    return user, message, history, deps


def finish_chat(user: sqlite3.Row | None, message: str, deps: ShopDeps, response: ChatResponse) -> ChatResponse:
    response.message = message
    response.redactions = deps.redactions
    if user:
        memory.save_turn(user["id"], message, response)  # stores the cleaned message only
    return response


def chat_error(e: Exception) -> tuple[int, str]:
    if isinstance(e, agent.AssistantUnavailable):
        log.error("Chat unavailable: %s", e)
        return 503, "Our assistant is offline right now. Please try again later."
    if isinstance(e, UsageLimitExceeded):
        return 502, "Sorry, that took me too long to look up. Could you ask in a simpler way?"
    log.exception("Chat failed")
    return 502, "Sorry, something went wrong on our end. Please try again."


@app.post("/api/chat")
async def chat(req: ChatRequest, cc_session: str | None = Cookie(default=None)) -> ChatResponse:
    """One chat turn → reply + product cards (no progress events)."""
    user, message, history, deps = prepare_chat(req, cc_session)
    try:
        response = await agent.chat(message, history, deps)
    except Exception as e:
        status, detail = chat_error(e)
        raise HTTPException(status_code=status, detail=detail)
    return finish_chat(user, message, deps, response)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, cc_session: str | None = Cookie(default=None)) -> StreamingResponse:
    """One chat turn as Server-Sent Events, so the widget can show progress right away:
        data: {"type": "status", "text": "Searching the catalogue for hoodie…"}
        data: {"type": "result", "data": {...ChatResponse...}}
        data: {"type": "error", "status": 502, "detail": "..."}"""
    user, message, history, deps = prepare_chat(req, cc_session)

    async def events():
        def sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        yield sse({"type": "status", "text": "Thinking…"})
        try:
            async for event in agent.chat_stream(message, history, deps):
                if event["type"] == "result":
                    response = finish_chat(user, message, deps, event["data"])
                    yield sse({"type": "result", "data": response.model_dump()})
                else:
                    yield sse(event)
        except Exception as e:
            status, detail = chat_error(e)
            yield sse({"type": "error", "status": status, "detail": detail})

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


def require_user(cc_session: str | None) -> sqlite3.Row:
    user = current_user(cc_session)
    if user is None:
        raise HTTPException(status_code=401, detail="Log in to see saved chats.")
    return user


@app.get("/api/chat/history")
def chat_history(cc_session: str | None = Cookie(default=None)) -> ChatHistory:
    """The logged-in shopper's saved chat (last 50 messages), with cards rebuilt from the database."""
    user = require_user(cc_session)
    return ChatHistory(messages=memory.load_history(user["id"]))


@app.delete("/api/chat/history")
def delete_chat_history(cc_session: str | None = Cookie(default=None)) -> dict:
    """Let shoppers erase their own saved chat."""
    user = require_user(cc_session)
    return {"deleted": memory.clear_history(user["id"])}
