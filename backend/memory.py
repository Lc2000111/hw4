"""Customer memory: chat history for logged-in shoppers, stored in the chat_messages table.

One row per message:
    id, user_id -> users.id, role ('user' | 'assistant'), content,
    products_json      the chat cards shown with an assistant reply (snapshot at the time),
    page_results_json  the search shown on the page with that reply (added in Problem 8),
    created_at

Snapshots record what the shopper saw, but on reload every card is rebuilt from the
current catalogue, so prices and stock shown are always today's.
Guests are never stored.
"""

from __future__ import annotations

import json
import sqlite3

import db
from models import ChatResponse, ChatTurn, PageResults, ProductCard, SearchFilters, StoredChatMessage

HISTORY_FOR_WIDGET = 50  # messages reloaded into the chat window


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Add the page_results_json column and an index (safe to run on every start)."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
    if "page_results_json" not in columns:
        conn.execute("ALTER TABLE chat_messages ADD COLUMN page_results_json TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages (user_id, id)")


def save_turn(user_id: int, message: str, response: ChatResponse) -> None:
    """Store the shopper's message and the assistant's reply (with its cards and page results)."""
    page = response.page_results
    page_json = (
        json.dumps({
            "search_id": page.search_id,
            "title": page.title,
            "filters": page.filters.model_dump(),
            "total_matches": page.total_matches,
            "product_ids": [p.product_id for p in page.products],
        })
        if page
        else None
    )
    with db.connect_rw() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
            (user_id, message),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json, page_results_json) "
            "VALUES (?, 'assistant', ?, ?, ?)",
            (user_id, response.reply, json.dumps([p.model_dump() for p in response.products]), page_json),
        )


def _rows(conn: sqlite3.Connection, user_id: int, limit: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE user_id = ? AND role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return list(reversed(rows))


def recent_turns(user_id: int, limit: int) -> list[ChatTurn]:
    """The last `limit` messages as plain text turns, oldest first, for the agent's history."""
    with db.connect() as conn:
        return [ChatTurn(role=r["role"], content=r["content"][:4000]) for r in _rows(conn, user_id, limit)]


def _ids(products_json: str | None) -> list[str]:
    try:
        items = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        return []
    return [i["product_id"] for i in items if isinstance(i, dict) and "product_id" in i]


def load_history(user_id: int, limit: int = HISTORY_FOR_WIDGET) -> list[StoredChatMessage]:
    """Saved messages for the chat widget, with cards and page results rebuilt from the database."""
    with db.connect() as conn:
        messages = []
        for r in _rows(conn, user_id, limit):
            products = [ProductCard.model_validate(p) for p in db.get_products(conn, _ids(r["products_json"]))]
            page_results = None
            if r["page_results_json"]:
                page = json.loads(r["page_results_json"])
                cards = [ProductCard.model_validate(p) for p in db.get_products(conn, page["product_ids"])]
                if cards:
                    page_results = PageResults(
                        search_id=page["search_id"],
                        title=page["title"],
                        filters=SearchFilters(**page["filters"]),
                        total_matches=page["total_matches"],
                        products=cards,
                    )
            messages.append(StoredChatMessage(
                id=r["id"], role=r["role"], content=r["content"], created_at=r["created_at"],
                products=products, page_results=page_results,
            ))
    return messages


def count_messages(user_id: int) -> int:
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()[0]


def previously_shown(user_id: int, limit: int) -> list[tuple[str, str]]:
    """(product_id, date last shown) for products shown as chat cards to this shopper, newest first."""
    seen: dict[str, str] = {}
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT products_json, created_at FROM chat_messages "
            "WHERE user_id = ? AND role = 'assistant' AND products_json IS NOT NULL ORDER BY id DESC",
            (user_id,),
        )
        for r in rows:
            for pid in _ids(r["products_json"]):
                seen.setdefault(pid, r["created_at"][:10])
            if len(seen) >= limit:
                break
    return list(seen.items())[:limit]


def clear_history(user_id: int) -> int:
    with db.connect_rw() as conn:
        return conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount
