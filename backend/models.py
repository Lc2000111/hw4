"""Pydantic / PydanticAI structured types for the Campus Customs shop assistant.

Four groups:
  1. Product data   - what tools return to the agent and what the website shows.
  2. Agent I/O      - the dependencies the agent runs with and its structured reply.
  3. Chat API       - the request/response bodies of POST /api/chat and the history endpoints.
  4. Audit trail    - one AuditEntry per agent-loop iteration (output/audit_trail.json).

Chat -> page contract (Problem 7):
  search_products returns a search_id  ->  the agent's ShopReply.show_on_page names that
  search_id + a title  ->  the backend sends ChatResponse.page_results with every match
  as a ProductCard built from the database  ->  the website renders them on the page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

Size = Literal["XS", "S", "M", "L", "XL", "XXL"]

# Broad product groups. The catalogue's own garment_type has 22 spellings
# ("hoodie", "pullover hoodie", "hooded sweatshirt"...), so tools map them to these.
Category = Literal["hoodie", "sweatshirt", "t-shirt", "long-sleeve", "quarter-zip", "jacket", "other"]

LOW_STOCK = 5  # "only N left" at or below this

# Stock status is decided in code, not by the model, so the threshold is always applied the same way.
StockStatus = Literal["in_stock", "low_stock", "sold_out"]
# For a size the shopper asked about: also "not_offered" when we don't make that size at all (e.g. 3XL).
RequestedSizeStatus = Literal["in_stock", "low_stock", "sold_out", "not_offered"]


# ---------------------------------------------------------------------------
# 1. Product data
# ---------------------------------------------------------------------------

class SizeStock(BaseModel):
    size: str
    quantity: int = Field(ge=0, description="Units on hand right now; 0 means sold out in this size.")


class ProductCard(BaseModel):
    """A product as the website shows it (Products grid, detail page, chat cards).
    Built from the database by the backend, never written by the model."""

    product_id: str
    name: str
    category: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    image_url: str
    price: float
    inventory: list[SizeStock]
    total_stock: int


class ProductInfo(BaseModel):
    """A product as a tool reports it to the agent: everything needed to answer
    honest questions about price, color, and stock."""

    product_id: str = Field(description="Exact id. Use it in product_ids to show the item to the shopper.")
    name: str
    category: Category
    garment_type: str
    short_description: str = Field(description="First sentence of the description (call get_product_info for all of it).")
    colors: list[str]
    price: float = Field(description="Price in US dollars, straight from the database.")
    stock_by_size: dict[str, int] = Field(description="Units on hand per size, e.g. {'XS': 0, 'S': 12, ...}.")
    sizes_in_stock: list[str]
    sizes_sold_out: list[str]
    low_stock_sizes: list[str] = Field(description=f"Sizes with {LOW_STOCK} or fewer units left (but not zero).")
    total_stock: int


class ProductDetails(BaseModel):
    """What get_product_info returns: the descriptive facts about one product, plus a
    short availability summary. Exact per-size counts come from check_stock."""

    product_id: str = Field(description="Exact id. Use it in product_ids to show the item to the shopper.")
    name: str
    category: Category = Field(description="Broad group (hoodie, sweatshirt, t-shirt, ...).")
    garment_type: str = Field(description="The catalogue's own wording, e.g. 'pullover hoodie'.")
    description: str = Field(description="Full product description from the catalogue. Paraphrase it; don't embellish.")
    colors: list[str]
    price: float = Field(description="Price in US dollars, straight from the database. Quote it exactly.")
    in_stock: bool = Field(description="True if at least one size has stock.")
    sizes_in_stock: list[str]
    sizes_sold_out: list[str]
    low_stock_sizes: list[str] = Field(description=f"Sizes with 1-{LOW_STOCK} units left.")
    total_stock: int = Field(description="Units on hand across all sizes.")


class SizeAvailability(BaseModel):
    size: str
    quantity: int = Field(ge=0, description="Exact units on hand.")
    status: StockStatus = Field(description=f"sold_out = 0, low_stock = 1-{LOW_STOCK}, in_stock = more.")


class StockReport(BaseModel):
    """What check_stock returns: live stock for one product, size by size."""

    product_id: str
    name: str
    price: float = Field(description="Price in US dollars, straight from the database.")
    requested_size: str | None = Field(
        description="The size the shopper asked about, normalized (e.g. 'medium' -> 'M'), or null if none was asked."
    )
    requested_size_status: RequestedSizeStatus | None = Field(
        description="Status of the requested size. 'sold_out' = say clearly it's sold out in that size. "
        "'not_offered' = we don't make that size at all. Null if no size was asked."
    )
    requested_size_quantity: int | None = Field(description="Exact units of the requested size, or null.")
    sizes: list[SizeAvailability] = Field(description="Every size we make for this product, XS to XXL.")
    sizes_in_stock: list[str]
    sizes_sold_out: list[str]
    total_stock: int
    summary: str = Field(description="One plain-English line stating the facts, safe to rely on.")


class SearchFilters(BaseModel):
    """The filters a search used; also shown on the page as "chips"."""

    query: str = ""
    category: str | None = None
    color: str | None = None
    max_price: float | None = None
    size: str | None = None


class SearchResults(BaseModel):
    """What search_products returns."""

    search_id: str = Field(
        description="Id of this search, e.g. 's1'. Put it in show_on_page to display ALL its matches on the website."
    )

    total_matches: int = Field(description="How many products matched before the limit was applied.")
    products: list[ProductInfo] = Field(description="Best matches first.")
    sold_out_in_requested_size: list[ProductInfo] = Field(
        default_factory=list,
        description="Products that match everything EXCEPT they are sold out in the requested size. "
        "They exist; tell the shopper honestly that the size is sold out and offer the sizes in stock.",
    )
    note: str | None = Field(default=None, description="Hints, e.g. why nothing matched.")


class CategorySummary(BaseModel):
    category: Category
    product_count: int
    min_price: float
    max_price: float


class ShopOverview(BaseModel):
    """What shop_overview returns: the shape of the whole catalogue."""

    total_products: int
    categories: list[CategorySummary]
    colors_available: list[str] = Field(description="Every color that appears on at least one product.")
    sizes: list[str]


# ---------------------------------------------------------------------------
# 2. Agent dependencies and structured output
# ---------------------------------------------------------------------------

@dataclass
class FactLog:
    """Every price, quantity, and product id the tools returned during one chat turn.
    The output validator in agent.py checks the reply against it, so the agent can't
    state a price or stock number that didn't come from the database."""

    prices: set[float] = field(default_factory=set)
    quantities: set[int] = field(default_factory=set)
    product_ids: set[str] = field(default_factory=set)


@dataclass
class SearchRecord:
    """A search made during this chat turn, kept so the page can show all of its matches
    (the model only sees the top few, the page can show them all)."""

    search_id: str
    filters: SearchFilters
    product_ids: list[str]  # every in-stock match, best first
    total_matches: int


class CustomerProfile(BaseModel):
    """Who is chatting (logged-in shoppers only). The ONLY customer fields the agent sees:
    never the password hash, session token, or other customers' data."""

    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Date the account was created, YYYY-MM-DD.")


PageType = Literal["home", "products", "product", "about", "login", "signup", "other"]


class PageContext(BaseModel):
    """Which page of the website the shopper is on when they send a message."""

    path: str = Field(default="/", max_length=300, description="URL path, e.g. '/products/basic-hoodie-big-yale'.")
    page_type: PageType = "other"
    product_id: str | None = Field(default=None, max_length=200, description="Set on a product page.")
    results_title: str | None = Field(
        default=None, max_length=80, description="Title of the chat results currently shown on the page, if any."
    )


@dataclass
class ShopDeps:
    """Per-request context handed to the agent and its tools.

    customer_id is used by tools to read THIS shopper's own chat memory; it is never
    shown to the model. customer is what the model may know about the shopper."""

    customer_id: int | None = None
    customer: CustomerProfile | None = None
    page: PageContext = field(default_factory=PageContext)
    redactions: list[str] = field(default_factory=list)  # kinds of sensitive data removed from this message
    facts: FactLog = field(default_factory=FactLog)
    searches: dict[str, SearchRecord] = field(default_factory=dict)


class PageDisplay(BaseModel):
    """The agent's request to show a search's matches on the website page."""

    search_id: str = Field(description="The search_id of the search_products call whose matches should fill the page.")
    title: str = Field(max_length=60, description="Short heading for the results, e.g. 'Hoodies' or 'Navy hoodies in M'.")


class ShopReply(BaseModel):
    """The agent's final answer for one chat turn."""

    reply: str = Field(description="What to say to the shopper, in the Campus Customs voice. Plain text, short.")
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
        description="Ids of specific products (from tool results only) to show as small cards inside the chat, "
        "most relevant first. Use for one or a few specific items. Empty if none.",
    )
    show_on_page: PageDisplay | None = Field(
        default=None,
        description="Set when the shopper is browsing a type or group of items (e.g. 'what hoodies do you have?'): "
        "the website then shows ALL matches of that search as product cards on the page. Null otherwise.",
    )


class AccountInfo(BaseModel):
    """What get_my_account returns."""

    logged_in: bool
    customer: CustomerProfile | None = None
    saved_messages: int = Field(0, description="How many chat messages are saved for this shopper.")
    note: str | None = None


class RememberedProduct(BaseModel):
    product_id: str
    name: str
    price: float = Field(description="Current price from the database (not the price at the time).")
    total_stock: int = Field(description="Current units in stock across all sizes.")
    last_shown: str = Field(description="When it was last shown to this shopper in chat, YYYY-MM-DD.")


class ChatMemory(BaseModel):
    """What recall_previous_products returns: products shown to this shopper in past chats."""

    logged_in: bool
    products: list[RememberedProduct] = Field(default_factory=list, description="Most recently shown first.")
    note: str | None = None


# ---------------------------------------------------------------------------
# 3. Chat API bodies
# ---------------------------------------------------------------------------

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(
        default_factory=list,
        max_length=40,
        description="Earlier turns, oldest first. Used for guests only; logged-in history comes from the database.",
    )
    page: PageContext = Field(default_factory=PageContext, description="The page the shopper is on.")


class PageResults(BaseModel):
    """Search matches for the website to render as product cards on the page."""

    search_id: str
    title: str
    filters: SearchFilters
    total_matches: int
    products: list[ProductCard] = Field(description="Every match (up to MAX_PAGE_RESULTS), built from the database.")


MAX_PAGE_RESULTS = 60


class ChatResponse(BaseModel):
    reply: str
    message: str | None = Field(default=None, description="The shopper's message as stored (after the sensitive-data guard).")
    redactions: list[str] = Field(default_factory=list, description="Kinds of sensitive data removed, e.g. ['card number'].")
    products: list[ProductCard] = Field(description="Small cards shown inside the chat, built from the database.")
    page_results: PageResults | None = Field(
        default=None, description="If set, the website shows these matches as product cards on the page."
    )


class StoredChatMessage(BaseModel):
    """One saved chat message, as reloaded into the chat widget."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    products: list[ProductCard] = Field(default_factory=list, description="Chat cards, rebuilt from the database.")
    page_results: PageResults | None = None


class ChatHistory(BaseModel):
    messages: list[StoredChatMessage]


# ---------------------------------------------------------------------------
# 4. Audit trail (Problem 12): one entry per agent-loop iteration, appended to
#    output/audit_trail.json and never rewritten or wiped.
# ---------------------------------------------------------------------------

AuditStopReason = Literal["continue", "final_output", "usage_limit", "content_filter", "safety_guard", "error"]


class AuditToolCall(BaseModel):
    tool_name: str
    args: dict[str, object] = Field(description="Arguments the model passed, long values shortened.")


class AuditToolResult(BaseModel):
    tool_name: str
    ok: bool = Field(description="False if the tool raised ModelRetry or the reply was rejected by a validator.")
    summary: str = Field(description="One short line, never the full payload and never personal data.")


class AuditEntry(BaseModel):
    """One iteration of the agent loop: model call → tool calls → tool results → stop or continue."""

    run_id: str = Field(description="Groups the iterations of one chat turn.")
    timestamp: str = Field(description="UTC time of the model response, ISO 8601.")
    iteration: int = Field(description="1 for the first model call in the turn, 2 for the next, ...")
    model: str
    customer_id: int | None = Field(description="Internal user id for logged-in shoppers, null for guests. No names or emails.")
    page: str = Field(description="Website path the shopper was on.")
    input: str = Field(description="The shopper's message AFTER the sensitive-data guard, shortened.")
    redactions: list[str] = Field(default_factory=list, description="Kinds of sensitive data removed from the input.")
    model_text: str | None = Field(default=None, description="Any plain text the model wrote alongside its tool calls.")
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    tool_results: list[AuditToolResult] = Field(default_factory=list)
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    stop_reason: AuditStopReason = Field(description="'continue' if the loop went on; otherwise why the turn stopped here.")
    stop_detail: str | None = Field(default=None, description="Final reply (shortened) or error message when the turn stops.")
    turn_ms: int | None = Field(default=None, description="Wall-clock time of the whole turn (on the last entry only).")
