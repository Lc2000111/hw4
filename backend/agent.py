"""Campus Customs shop assistant - agent entry and wiring.

The agent is built from:
  - the system prompt in prompts/prompt.md (read at startup),
  - an OpenAI model routed through Portkey (PORTKEY_API_KEY from .env),
  - the tools in tools.py and the structured types in models.py.

main.py calls `chat()` for every message from the website's chat widget.

Quick test from the backend/ folder:
    python agent.py "Do you have navy hoodies in medium?"
"""

from __future__ import annotations

import os
import re
import sys
import time
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from dotenv import find_dotenv, load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, ToolOutput, UsageLimitExceeded, UsageLimits
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

import audit
import db
import safety
from models import ChatResponse, ChatTurn, FactLog, PageResults, ProductCard, ShopDeps, ShopReply
from tools import TOOLS

# Loads the nearest .env, searching up from this file (backend/ → hw4/ → class folder).
load_dotenv(find_dotenv())

PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt.md"
MODEL_NAME = os.getenv("PORTKEY_MODEL", "gpt-5.6-luna")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

MAX_HISTORY_TURNS = 12  # older turns are dropped to keep requests small
# Stopping rules for one chat turn: a few tool calls, then answer.
LIMITS = UsageLimits(request_limit=8, tool_calls_limit=10)

# Numbers in a reply that must match what the tools returned this turn.
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
QUANTITY_RE = re.compile(r"\b(\d{1,4})\s+(?:left|in stock|units?|available|remaining|pieces?)\b", re.IGNORECASE)

# Said when the model provider's safety filter blocks a message (e.g. a jailbreak attempt).
FILTERED_REPLY = (
    "Sorry, I can't help with that one. I'm happy to help you find hoodies, tees, "
    "or anything else in the Campus Customs shop, though!"
)


class AssistantUnavailable(RuntimeError):
    """Raised when the model can't be used (e.g. no API key configured)."""


def make_model() -> OpenAIChatModel:
    """OpenAI model routed through Portkey; the key only ever comes from the environment."""
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise AssistantUnavailable("PORTKEY_API_KEY is not set. Add it to a .env file (see .env.example).")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_agent() -> Agent[ShopDeps, ShopReply]:
    """Build the agent once, on first use, so the API can start even without a key."""
    agent = Agent(
        make_model(),
        deps_type=ShopDeps,
        # The reply is returned through a "final_result" tool; up to 3 fix-ups if the fact check rejects it.
        output_type=ToolOutput(ShopReply, name="final_result", max_retries=3),
        instructions=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=TOOLS,
        retries=2,
        name="campus_customs_assistant",
    )

    @agent.instructions
    def customer_context(ctx: RunContext[ShopDeps]) -> str:
        """Who is chatting, from ShopDeps.customer (filled from the session in main.py)."""
        c = ctx.deps.customer
        if c is None:
            return "## Who you're chatting with\nA guest (not logged in). Their chat is not saved."
        return (
            "## Who you're chatting with\n"
            f"A logged-in customer: {c.first_name} {c.last_name}, email {c.email}, member since {c.member_since}. "
            "Their earlier messages (if any) are included above, and this conversation is saved to their account. "
            "You may greet them by first name. Only mention their email if they ask about their own account."
        )

    @agent.instructions
    def safety_context(ctx: RunContext[ShopDeps]) -> str:
        """Tell the model when the sensitive-data guard removed something from this message."""
        if not ctx.deps.redactions:
            return ""
        kinds = ", ".join(ctx.deps.redactions)
        return (
            f"## Sensitive data removed\nFor the shopper's safety, a {kinds} was removed from their message before "
            "you saw it. Briefly tell them not to share that in chat, that we can't take payments or account "
            "changes in chat, and then help with the rest of their message."
        )

    @agent.instructions
    def page_context(ctx: RunContext[ShopDeps]) -> str:
        """What page the shopper is on. On a product page this runs a database lookup, so the
        model knows exactly which item 'this' or 'it' means, including its real colors."""
        page = ctx.deps.page
        lines = [f"## Page the shopper is on\nPath {page.path} ({page.page_type} page)."]
        if page.product_id:
            with db.connect() as conn:
                product = db.get_product(conn, page.product_id)
            if product:
                # Speed: preload this item's live price and stock, so questions about "this" need no
                # tool round trip. They come from the database right now, so they count as checked facts.
                facts = ctx.deps.facts
                facts.product_ids.add(product["product_id"])
                facts.prices.add(float(product["price"]))
                facts.quantities.add(product["total_stock"])
                facts.quantities.update(s["quantity"] for s in product["inventory"])
                stock = ", ".join(
                    f"{s['size']} sold out" if s["quantity"] == 0
                    else f"{s['size']} {s['quantity']} (only {s['quantity']} left)" if s["quantity"] <= db.LOW_STOCK
                    else f"{s['size']} {s['quantity']}"
                    for s in product["inventory"]
                )
                lines.append(
                    f"They are looking at: {product['name']} (product_id '{product['product_id']}', "
                    f"{product['garment_type']}), colors: {', '.join(product['colors'])}.\n"
                    f"LIVE from the database right now: price ${product['price']:.2f}; stock by size: {stock}; "
                    f"total {product['total_stock']}.\n"
                    "If they say 'this', 'it', or 'this one', they mean this item. These live facts are authoritative "
                    "and were just read from the database: do NOT call check_stock or get_product_info for this item. "
                    "Reply with final_result right away (put this product_id in product_ids). "
                    "Use tools only for OTHER products or searches."
                )
        if page.results_title:
            lines.append(f"The page is currently showing chat results titled '{page.results_title}'.")
        return "\n".join(lines)

    @agent.output_validator
    def only_database_numbers(ctx: RunContext[ShopDeps], output: ShopReply) -> ShopReply:
        """Reject replies that quote a price or stock number no tool returned this turn,
        or that ask to show a search on the page that wasn't run this turn."""
        if output.show_on_page and output.show_on_page.search_id not in ctx.deps.searches:
            known = ", ".join(ctx.deps.searches) or "none yet"
            raise ModelRetry(
                f"show_on_page.search_id '{output.show_on_page.search_id}' doesn't match a search from this turn "
                f"(searches this turn: {known}). Call search_products and use its search_id, or set show_on_page to null."
            )
        unverified = unverified_numbers(output.reply, ctx.deps.facts)
        if unverified:
            raise ModelRetry(
                f"Your reply states {', '.join(unverified)}, but no tool returned that number in this turn. "
                "Look it up with get_product_info or check_stock (stock may have changed since earlier messages), "
                "and only state prices and quantities exactly as the tools return them."
            )
        return output

    return agent


def unverified_numbers(reply: str, facts: FactLog) -> list[str]:
    """Prices ("$68") and stock counts ("only 2 left") in the reply that the tools never returned."""
    bad = []
    for m in PRICE_RE.finditer(reply):
        if float(m.group(1).replace(",", "")) not in facts.prices:
            bad.append(m.group(0))
    for m in QUANTITY_RE.finditer(reply):
        if int(m.group(1)) not in facts.quantities:
            bad.append(f'"{m.group(0)}"')
    return bad


def to_model_history(history: list[ChatTurn]) -> list[ModelMessage]:
    """Turn the widget's earlier turns into PydanticAI messages (only plain text, never tool calls)."""
    messages: list[ModelMessage] = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.content)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.content)]))
    return messages


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Build cards from the database for the ids the agent chose; unknown ids are dropped.
    Prices and stock on the cards therefore always come from the database, not the model."""
    cards: list[ProductCard] = []
    seen: set[str] = set()
    with db.connect() as conn:
        for pid in product_ids:
            if pid in seen:
                continue
            seen.add(pid)
            product = db.get_product(conn, pid)
            if product is not None:
                cards.append(ProductCard.model_validate(product))
    return cards


def describe_tool_call(call: ToolCallPart) -> str:
    """A friendly progress line for the chat widget while a tool runs."""
    args = call.args_as_dict()
    product = str(args.get("product", "")).replace("-", " ").strip()
    if call.tool_name == "search_products":
        what = " ".join(str(args[k]) for k in ("color", "category", "query") if args.get(k)).strip()
        return f"Searching the catalogue for {what}…" if what else "Searching the catalogue…"
    if call.tool_name == "check_stock":
        size = f" in {args['size']}" if args.get("size") else ""
        return f"Checking stock for {product or 'that item'}{size}…"
    if call.tool_name == "get_product_info":
        return f"Looking up {product or 'that item'}…"
    if call.tool_name == "shop_overview":
        return "Looking over the whole catalogue…"
    if call.tool_name == "get_my_account":
        return "Checking your account…"
    if call.tool_name == "recall_previous_products":
        return "Looking through your past chats…"
    return "Working on it…"


async def chat_stream(message: str, history: list[ChatTurn], deps: ShopDeps) -> AsyncIterator[dict]:
    """Run one chat turn and yield progress events as it goes:
        {"type": "status", "text": "Checking stock for basic hoodie big yale in XL…"}  (zero or more)
        {"type": "result", "data": ChatResponse}                                      (last)
    """
    # Dollar amounts the shopper typed (e.g. a budget) may be repeated back; anything else must come from tools.
    deps.facts.prices.update(float(m.group(1).replace(",", "")) for m in PRICE_RE.finditer(message))
    started = time.perf_counter()
    run = None

    # Safety guard in code: crisis language gets a caring, fixed reply with crisis resources,
    # no model call and no selling (the provider filter would otherwise block it with a generic refusal).
    if safety.is_crisis(message):
        audit.record([], deps, message, "safety_guard", "Crisis language detected: sent crisis resources (988).", started, MODEL_NAME)
        yield {"type": "result", "data": ChatResponse(reply=safety.CRISIS_REPLY, products=[])}
        return

    agent = get_agent()

    def audit_turn(reason, detail: str | None) -> None:
        """Append this turn's loop iterations to output/audit_trail.json (append-only)."""
        messages = run.new_messages() if run is not None else []
        audit.record(messages, deps, message, reason, detail, started, MODEL_NAME)

    try:
        async with agent.iter(
            message, deps=deps, message_history=to_model_history(history), usage_limits=LIMITS
        ) as run:
            async for node in run:
                if Agent.is_call_tools_node(node):
                    for part in node.model_response.parts:
                        if isinstance(part, ToolCallPart) and part.tool_name != "final_result":
                            yield {"type": "status", "text": describe_tool_call(part)}
            result = run.result
    except ModelHTTPError as e:
        if e.status_code == 400 and "content_filter" in str(e.body):
            audit_turn("content_filter", "Blocked by the model provider's content filter; shopper got a polite refusal.")
            yield {"type": "result", "data": ChatResponse(reply=FILTERED_REPLY, products=[])}
            return
        audit_turn("error", f"Model HTTP {e.status_code}")
        raise
    except UsageLimitExceeded as e:
        audit_turn("usage_limit", str(e))
        raise
    except Exception as e:
        audit_turn("error", f"{type(e).__name__}: {e}")
        raise
    audit_turn("final_output", result.output.reply)
    yield {"type": "result", "data": build_response(result.output, deps)}


async def chat(message: str, history: list[ChatTurn], deps: ShopDeps) -> ChatResponse:
    """Run one chat turn without progress events (same code path as chat_stream)."""
    response = None
    async for event in chat_stream(message, history, deps):
        if event["type"] == "result":
            response = event["data"]
    assert response is not None
    return response


def build_response(reply: ShopReply, deps: ShopDeps) -> ChatResponse:
    # Cards only for products a tool actually returned this turn (or the page being viewed).
    allowed = deps.facts.product_ids | {deps.page.product_id}
    return ChatResponse(
        reply=reply.reply,
        products=product_cards([p for p in reply.product_ids if p in allowed]),
        page_results=page_results(reply, deps),
    )


def page_results(reply: ShopReply, deps: ShopDeps) -> PageResults | None:
    """Turn the agent's show_on_page choice into product cards for the website page.
    The products are the search's own matches, rebuilt from the database, not ids typed by the model."""
    if reply.show_on_page is None:
        return None
    search = deps.searches.get(reply.show_on_page.search_id)
    if search is None or not search.product_ids:
        return None
    return PageResults(
        search_id=search.search_id,
        title=reply.show_on_page.title.strip() or "Matches from chat",
        filters=search.filters,
        total_matches=search.total_matches,
        products=product_cards(search.product_ids),
    )


if __name__ == "__main__":
    import asyncio

    question = " ".join(sys.argv[1:]) or "What hoodies do you have?"
    response = asyncio.run(chat(question, [], ShopDeps()))
    print(response.reply)
    for card in response.products:
        print(f"  - {card.name} (${card.price:.0f}, {card.total_stock} in stock)")
