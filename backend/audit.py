"""Append-only audit trail of agent-loop activity (Problem 12).

Every chat turn appends one AuditEntry per agent-loop iteration to
output/audit_trail.json: when the model was called, which tools it called with
which (shortened) arguments, a one-line summary of each result, token use, and
why the loop continued or stopped.

Append-only: the file is a JSON array that only grows. New entries are written
just before the closing "]"; existing entries are never rewritten, reordered,
or deleted, and nothing wipes the file between runs or server restarts.
Privacy: no names, emails, passwords, or card numbers. The input is logged
AFTER the sensitive-data guard, and account tools are summarized without
personal details.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import UTC, datetime

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

import db
from models import (
    AccountInfo,
    AuditEntry,
    AuditStopReason,
    AuditToolCall,
    AuditToolResult,
    ChatMemory,
    ProductDetails,
    SearchResults,
    ShopDeps,
    ShopOverview,
    StockReport,
)

AUDIT_PATH = db.ROOT / "output" / "audit_trail.json"
SHORT = 160  # max characters for any logged text

log = logging.getLogger("campus_customs.audit")
_lock = threading.Lock()


def _short(text: object, limit: int = SHORT) -> str:
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _short_args(args: dict) -> dict[str, object]:
    return {k: (_short(v, 60) if isinstance(v, str) else v) for k, v in args.items() if v not in (None, "")}


def summarize(part: ToolReturnPart | RetryPromptPart) -> AuditToolResult:
    """One safe, readable line per tool result."""
    if isinstance(part, RetryPromptPart):
        what = "reply rejected" if part.tool_name == "final_result" else "retry"
        return AuditToolResult(tool_name=part.tool_name or "?", ok=False, summary=f"{what}: {_short(part.model_response())}")
    c = part.content
    if isinstance(c, SearchResults):
        top = ", ".join(p.product_id for p in c.products[:3])
        extra = f"; sold out in size: {len(c.sold_out_in_requested_size)}" if c.sold_out_in_requested_size else ""
        s = f"{c.search_id}: {c.total_matches} matches; top: {top or 'none'}{extra}"
    elif isinstance(c, StockReport):
        s = c.summary
    elif isinstance(c, ProductDetails):
        s = f"{c.product_id}: ${c.price:.2f}, in stock {','.join(c.sizes_in_stock) or 'none'}"
    elif isinstance(c, ShopOverview):
        s = f"{c.total_products} products in {len(c.categories)} categories"
    elif isinstance(c, AccountInfo):
        s = f"logged_in={c.logged_in}, saved_messages={c.saved_messages}"  # never the name or email
    elif isinstance(c, ChatMemory):
        s = f"{len(c.products)} previously shown products"
    elif part.tool_name == "final_result":
        s = "reply accepted"
    else:
        s = str(c)
    return AuditToolResult(tool_name=part.tool_name, ok=True, summary=_short(s))


def build_entries(
    messages: list[ModelMessage],
    deps: ShopDeps,
    message: str,
    stop_reason: AuditStopReason,
    stop_detail: str | None,
    turn_ms: int,
    model_name: str,
) -> list[AuditEntry]:
    """Turn one run's new messages into one AuditEntry per model call."""
    run_id = uuid.uuid4().hex[:12]
    results: dict[str, ToolReturnPart | RetryPromptPart] = {}
    for m in messages:
        if isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, (ToolReturnPart, RetryPromptPart)) and p.tool_call_id:
                    results[p.tool_call_id] = p

    common = dict(
        run_id=run_id,
        model=model_name,
        customer_id=deps.customer_id,
        page=deps.page.path,
        input=_short(message, 200),
        redactions=deps.redactions,
    )
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    if not responses:  # e.g. the very first model call was blocked or failed
        now = datetime.now(UTC).isoformat(timespec="seconds")
        return [AuditEntry(**common, timestamp=now, iteration=1, stop_reason=stop_reason,
                           stop_detail=_short(stop_detail or ""), turn_ms=turn_ms)]

    entries = []
    for n, resp in enumerate(responses, 1):
        calls = [p for p in resp.parts if isinstance(p, ToolCallPart)]
        text = " ".join(p.content for p in resp.parts if isinstance(p, TextPart)).strip()
        last = n == len(responses)
        entries.append(AuditEntry(
            **common,
            timestamp=resp.timestamp.astimezone(UTC).isoformat(timespec="seconds"),
            iteration=n,
            model_text=_short(text) if text else None,
            tool_calls=[AuditToolCall(tool_name=c.tool_name, args=_short_args(c.args_as_dict()))
                        for c in calls if c.tool_name != "final_result"],
            tool_results=[summarize(results[c.tool_call_id]) for c in calls if c.tool_call_id in results],
            input_tokens=resp.usage.input_tokens,
            cached_tokens=resp.usage.cache_read_tokens,
            output_tokens=resp.usage.output_tokens,
            stop_reason=stop_reason if last else "continue",
            stop_detail=_short(stop_detail) if last and stop_detail else None,
            turn_ms=turn_ms if last else None,
        ))
    return entries


def append(entries: list[AuditEntry]) -> None:
    """Append entries to the JSON array on disk without touching existing entries."""
    if not entries:
        return
    payload = ",\n".join(e.model_dump_json() for e in entries)
    with _lock:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
            AUDIT_PATH.write_text(f"[\n{payload}\n]\n", encoding="utf-8")
            return
        with open(AUDIT_PATH, "rb+") as f:
            f.seek(0, 2)
            size = f.tell()
            back = min(size, 4096)
            f.seek(size - back)
            tail = f.read()
            end = tail.rfind(b"]")
            if end == -1:
                # Not a JSON array (e.g. edited by hand): keep it untouched and start a new file beside it.
                log.error("audit_trail.json is not a JSON array; leaving it as is")
                return
            before = tail[:end].rstrip()
            empty = before.endswith(b"[")
            f.seek(size - back + end)
            f.truncate()  # removes only the closing "]" (and trailing whitespace)
            f.write(((("\n" if empty else ",\n") + payload + "\n]\n")).encode("utf-8"))


def record(
    messages: list[ModelMessage],
    deps: ShopDeps,
    message: str,
    stop_reason: AuditStopReason,
    stop_detail: str | None,
    started: float,
    model_name: str,
) -> None:
    """Build and append the audit entries for one chat turn. Never breaks the chat if logging fails."""
    try:
        turn_ms = int((time.perf_counter() - started) * 1000)
        append(build_entries(messages, deps, message, stop_reason, stop_detail, turn_ms, model_name))
    except Exception:
        log.exception("Could not write the audit trail")


def read_all() -> list[dict]:
    """Helper for tests and reviews."""
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8")) if AUDIT_PATH.exists() else []
