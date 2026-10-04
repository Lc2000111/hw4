"""Tools the Campus Customs assistant can call.

Every fact the assistant states about a product (description, price, colors,
sizes, stock) must come from one of these tools, and every tool reads the live
database read-only. The tools never touch the users or sessions tables.

    search_products      find products by keywords and filters ("navy hoodies in M?")
    get_product_info     one product's description, price, colors, availability
    check_stock          one product's stock size by size ("is it in XS?", "how many L?")
    shop_overview        the whole catalogue at a glance (categories, prices, colors)
    get_my_account       who is chatting: name, email, member since (logged-in shoppers)
    recall_previous_products   products shown to THIS shopper in earlier chats

Each tool also records the prices, quantities, and ids it returned in
ctx.deps.facts, so agent.py can reject a reply that quotes a number the
database never gave.
"""

from __future__ import annotations

import difflib
import re

from pydantic_ai import ModelRetry, RunContext

import db
import memory
from db import category_of
from models import (
    LOW_STOCK,
    AccountInfo,
    ChatMemory,
    RememberedProduct,
    MAX_PAGE_RESULTS,
    Category,
    CategorySummary,
    ProductDetails,
    ProductInfo,
    SearchFilters,
    SearchRecord,
    SearchResults,
    ShopDeps,
    ShopOverview,
    SizeAvailability,
    StockReport,
    StockStatus,
)

MAX_RESULTS = 8

# Words that carry no product meaning in a search.
STOPWORDS = {
    "a", "an", "and", "any", "are", "do", "for", "have", "i", "in", "is", "it", "me", "my", "of", "on",
    "or", "show", "some", "something", "similar", "like", "the", "to", "want", "with", "you", "your", "campus", "customs",
    "merch", "apparel", "shirt", "shirts", "item", "items", "size", "color", "colour",
}

# Shopper words -> words used in the catalogue.
SYNONYMS = {
    "hoodie": ["hoodie", "hooded"],
    "hoody": ["hoodie", "hooded"],
    "tee": ["t-shirt"],
    "tshirt": ["t-shirt"],
    "crew": ["crewneck", "crew"],
    "sweater": ["sweater", "sweatshirt", "crewneck"],
    "grey": ["gray"],
    "dog": ["bulldog"],
    "quarter": ["quarter-zip", "1-4"],
    "zip": ["zip"],
}

COLOR_ALIASES = {"grey": "gray", "charcoal": "charcoal", "beige": "cream"}

# How shoppers say sizes -> our size codes.
SIZE_WORDS = {
    "xs": "XS", "x-small": "XS", "xsmall": "XS", "extra small": "XS", "extra-small": "XS",
    "s": "S", "sm": "S", "small": "S",
    "m": "M", "med": "M", "medium": "M",
    "l": "L", "lg": "L", "large": "L",
    "xl": "XL", "x-large": "XL", "xlarge": "XL", "extra large": "XL", "extra-large": "XL",
    "xxl": "XXL", "2xl": "XXL", "2x": "XXL", "xx-large": "XXL", "xxlarge": "XXL",
    "double xl": "XXL", "extra extra large": "XXL", "2x-large": "XXL",
}


# ---------- helpers ----------

def normalize_size(text: str) -> str | None:
    """'medium' -> 'M', '2XL' -> 'XXL'; None if it isn't one of the sizes we make."""
    return SIZE_WORDS.get(" ".join(text.lower().replace("_", " ").split()))


def stock_status(quantity: int) -> StockStatus:
    if quantity == 0:
        return "sold_out"
    if quantity <= LOW_STOCK:
        return "low_stock"
    return "in_stock"


def category_from_words(text: str) -> Category | None:
    """Map a shopper's garment word (e.g. 'tee', 'crewneck', '1/4 zip') to a category."""
    t = text.lower().replace("/", "-").replace(" ", "-")
    # Order matters: "sweatshirt" contains "tshirt", and "crew-neck t-shirt" is a tee.
    rules: list[tuple[tuple[str, ...], Category]] = [
        (("quarter", "1-4"), "quarter-zip"),
        (("jacket", "fleece", "bomber", "coat"), "jacket"),
        (("hood",), "hoodie"),
        (("sweatshirt", "sweater"), "sweatshirt"),
        (("tee", "t-shirt", "tshirt"), "t-shirt"),
        (("long-sleeve", "long-sleeved", "performance"), "long-sleeve"),
        (("crew", "mock"), "sweatshirt"),
    ]
    for keys, category in rules:
        if any(k in t for k in keys):
            return category
    return None


def short_text(text: str, limit: int = 110) -> str:
    """First sentence, capped, so search results stay small (fewer tokens = faster, cheaper replies)."""
    first = text.split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[: limit - 1].rsplit(" ", 1)[0] + "…"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# How shoppers write garment words vs. how catalogue names spell them (found via the audit trail:
# "Boola Boola Tee" missed "Boola Boola T Shirt" and cost two extra model calls).
NAME_SYNONYMS = [
    (r"\b(tee|tshirt|t-shirt)\b", "t shirt"),
    (r"\bcrew[ -]neck\b", "crewneck"),
    (r"\b(quarter[ -]zip|1/4[ -]zip|quarterzip)\b", "1 4 zip"),
    (r"\bhoody\b", "hoodie"),
]


def _canonical_name(text: str) -> str:
    t = text.lower()
    for pattern, repl in NAME_SYNONYMS:
        t = re.sub(pattern, repl, t)
    return t


def resolve_product(conn, ref: str) -> dict:
    """Find a product by exact id, by name, or by a name typed like an id.
    Unknown references raise ModelRetry with the closest real names."""
    ref = ref.strip()
    product = (db.get_product(conn, ref) or db.get_product(conn, _slug(ref))
               or db.get_product(conn, _slug(_canonical_name(ref))))
    if product:
        return product
    names = {r["name"].lower(): r["product_id"] for r in conn.execute("SELECT product_id, name FROM catalogue")}
    if ref.lower() in names:
        return db.get_product(conn, names[ref.lower()])
    # A short name like "Davenport crewneck": accept it if exactly one product name has all its words.
    words = set(_slug(_canonical_name(ref)).split("-")) - {"the", "yale"}
    hits = [pid for name, pid in names.items() if words and words <= set(_slug(name).split("-"))]
    if len(hits) == 1:
        return db.get_product(conn, hits[0])
    close = difflib.get_close_matches(_canonical_name(ref), list(names), n=3, cutoff=0.5)
    # One clearly-closest name (e.g. a small typo) is accepted instead of costing a retry round trip.
    if close and difflib.SequenceMatcher(None, _canonical_name(ref), close[0]).ratio() >= 0.9:
        return db.get_product(conn, names[close[0]])
    hint = f" Closest names: {', '.join(repr(c) for c in close)}." if close else ""
    raise ModelRetry(f"No product matches '{ref}'.{hint} Use search_products to find the right product_id.")


def _new_search_id(ctx: RunContext[ShopDeps] | None) -> str:
    return f"s{len(ctx.deps.searches) + 1}" if ctx is not None else "s0"


def _record(ctx: RunContext[ShopDeps] | None, product: dict) -> None:
    """Remember the facts a tool returned, for the reply check in agent.py."""
    if ctx is None:
        return
    facts = ctx.deps.facts
    facts.product_ids.add(product["product_id"])
    facts.prices.add(float(product["price"]))
    facts.quantities.add(product["total_stock"])
    facts.quantities.update(s["quantity"] for s in product["inventory"])


def to_info(product: dict) -> ProductInfo:
    stock = {s["size"]: s["quantity"] for s in product["inventory"]}
    return ProductInfo(
        product_id=product["product_id"],
        name=product["name"],
        category=category_of(product["garment_type"]),
        garment_type=product["garment_type"],
        short_description=short_text(product["description"]),
        colors=product["colors"],
        price=product["price"],
        stock_by_size=stock,
        sizes_in_stock=[s for s, q in stock.items() if q > 0],
        sizes_sold_out=[s for s, q in stock.items() if q == 0],
        low_stock_sizes=[s for s, q in stock.items() if 0 < q <= LOW_STOCK],
        total_stock=product["total_stock"],
    )


def _terms(query: str) -> list[list[str]]:
    """Split a query into terms; each term is a list of acceptable spellings."""
    terms = []
    for word in re.findall(r"[a-z0-9\-]+", query.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        if word.endswith("s") and len(word) > 3 and not word.endswith("ss"):
            word = word[:-1]  # hoodies -> hoodie
        terms.append(SYNONYMS.get(word, [word]))
    return terms


def _score(product: dict, terms: list[list[str]]) -> tuple[int, int]:
    """(how many query terms matched, weighted score). Name/type/tags count more than description."""
    strong = " ".join([product["name"], product["garment_type"], *product["search_tags"]]).lower()
    colors = " ".join(product["colors"]).lower()
    desc = product["description"].lower()
    matched = score = 0
    for spellings in terms:
        best = 0
        for s in spellings:
            if s in strong:
                best = max(best, 3)
            elif s in colors:
                best = max(best, 2)
            elif s in desc:
                best = max(best, 1)
        if best:
            matched += 1
            score += best
    return matched, score


# ---------- tools ----------

def search_products(
    ctx: RunContext[ShopDeps],
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    size: str | None = None,
    limit: int = MAX_RESULTS,
) -> SearchResults:
    """Search the Campus Customs catalogue with live prices and stock.

    Use for "do you have..." and browsing questions. For one specific item, use get_product_info or check_stock.
    You see the top matches; the returned search_id lets the website show ALL matches (put it in show_on_page).

    Args:
        query: Free-text keywords, e.g. "bulldog", "hockey", "Davenport", "Harvard Yale". Can be empty.
        category: Optional garment kind: hoodie, sweatshirt (crewnecks), t-shirt, long-sleeve, quarter-zip, jacket.
        color: Optional color the product must come in, e.g. "navy", "gray", "white".
        max_price: Optional highest price in US dollars.
        size: Optional size that must be IN STOCK, e.g. "M", "medium", "XL", "2XL".
        limit: How many products to return (1-8).
    """
    wanted_category = None
    if category:
        wanted_category = category_from_words(category)
        if wanted_category is None:
            raise ModelRetry(
                f"Unknown category '{category}'. Use one of: hoodie, sweatshirt, t-shirt, long-sleeve, quarter-zip, "
                "jacket, or leave it empty and put the word in query."
            )
    wanted_size = normalize_size(size) if size else None
    filters = SearchFilters(query=query, category=wanted_category, color=color, max_price=max_price, size=wanted_size or size)
    search_id = _new_search_id(ctx)
    if size and wanted_size is None:
        return SearchResults(
            search_id=search_id,
            total_matches=0,
            products=[],
            note=f"We don't make size '{size}'. Our sizes are {', '.join(db.SIZE_ORDER)}. Tell the shopper plainly.",
        )
    wanted_color = COLOR_ALIASES.get(color.strip().lower(), color.strip().lower()) if color else None
    limit = max(1, min(limit, MAX_RESULTS))
    terms = _terms(query)
    if max_price is not None and ctx is not None:
        ctx.deps.facts.prices.add(float(max_price))  # the shopper's budget may be repeated back

    with db.connect() as conn:
        products = db.all_products(conn)

    candidates = []
    for p in products:
        if wanted_category and category_of(p["garment_type"]) != wanted_category:
            continue
        if wanted_color and not any(wanted_color in c.lower() for c in p["colors"]):
            continue
        if max_price is not None and p["price"] > max_price:
            continue
        matched, score = _score(p, terms) if terms else (0, 0)
        if terms and matched == 0:
            continue
        candidates.append((matched, score, p))

    # Keep only the best-matching tier: products matching ALL keywords if any do, otherwise
    # the ones matching the most. ("bulldog crewneck" -> bulldog crewnecks, not every crewneck.)
    # This matters because the page shows every match, not just the top few.
    top = max((m for m, _, _ in candidates), default=0)
    candidates = [c for c in candidates if c[0] == top]

    ranked, sold_out = [], []
    for c in candidates:
        p = c[2]
        if wanted_size and not any(s["size"] == wanted_size and s["quantity"] > 0 for s in p["inventory"]):
            sold_out.append(c)  # exists, but not in this size: report it, don't hide it
        else:
            ranked.append(c)
    ranked.sort(key=lambda r: (-r[1], r[2]["name"]))
    sold_out = sorted(sold_out, key=lambda r: (-r[1], r[2]["name"]))[:3] if terms else []

    shown = [p for _, _, p in ranked[:limit]] + [p for _, _, p in sold_out]
    for p in shown:
        _record(ctx, p)
    if ctx is not None:
        ctx.deps.facts.quantities.add(len(ranked))
        # Keep every match so the page can show more than the model sees.
        page_ids = [p["product_id"] for _, _, p in ranked[:MAX_PAGE_RESULTS]]
        ctx.deps.facts.product_ids.update(page_ids)
        ctx.deps.searches[search_id] = SearchRecord(search_id, filters, page_ids, len(ranked))

    note = None
    if not ranked and not sold_out:
        note = "No products match all of these filters. Try fewer filters, or tell the shopper honestly that we don't carry it."
        if wanted_color:
            note += " Use shop_overview to see which colors exist."
    return SearchResults(
        search_id=search_id,
        total_matches=len(ranked),
        products=[to_info(p) for _, _, p in ranked[:limit]],
        sold_out_in_requested_size=[to_info(p) for _, _, p in sold_out],
        note=note,
    )


def get_product_info(ctx: RunContext[ShopDeps], product: str) -> ProductDetails:
    """Look up one product's description, price, colors, and which sizes are available.

    Use for "tell me about...", "how much is...", "what colors...", or "what is this made like?" questions.

    Args:
        product: The product_id (e.g. "basic-hoodie-big-yale") or its exact name (e.g. "Basic Hoodie Big Yale").
    """
    with db.connect() as conn:
        p = resolve_product(conn, product)
    _record(ctx, p)
    info = to_info(p)
    return ProductDetails(
        product_id=info.product_id,
        name=info.name,
        category=info.category,
        garment_type=info.garment_type,
        description=p["description"],
        colors=info.colors,
        price=info.price,
        in_stock=info.total_stock > 0,
        sizes_in_stock=info.sizes_in_stock,
        sizes_sold_out=info.sizes_sold_out,
        low_stock_sizes=info.low_stock_sizes,
        total_stock=info.total_stock,
    )


def check_stock(ctx: RunContext[ShopDeps], product: str, size: str | None = None) -> StockReport:
    """Check live stock for one product, size by size.

    Use for "is it in stock?", "do you have it in M?", "how many XL are left?", "what sizes are available?".
    Call it before confirming a size for any product, even if stock was mentioned earlier in the chat,
    EXCEPT the product the shopper is viewing: its live stock is already in the page context.

    Args:
        product: The product_id (e.g. "basic-hoodie-big-yale") or its exact name.
        size: Optional size the shopper asked about, e.g. "M", "medium", "XL", "2XL". Leave empty for all sizes.
    """
    with db.connect() as conn:
        p = resolve_product(conn, product)
    _record(ctx, p)

    sizes = [SizeAvailability(size=s["size"], quantity=s["quantity"], status=stock_status(s["quantity"]))
             for s in p["inventory"]]
    in_stock = [s.size for s in sizes if s.quantity > 0]
    sold_out = [s.size for s in sizes if s.quantity == 0]

    requested = requested_status = requested_qty = None
    if size:
        requested = normalize_size(size)
        match = next((s for s in sizes if s.size == requested), None)
        if match is None:
            requested, requested_status = size.strip(), "not_offered"
        else:
            requested_status, requested_qty = match.status, match.quantity

    def label(s: SizeAvailability) -> str:
        return f"{s.size} (only {s.quantity} left)" if s.status == "low_stock" else f"{s.size} ({s.quantity})"

    parts = [f"{p['name']} (${p['price']:.2f})"]
    if requested_status == "not_offered":
        parts.append(f"we don't make size '{requested}'; sizes are {', '.join(db.SIZE_ORDER)}")
    elif requested_status == "sold_out":
        parts.append(f"{requested} is SOLD OUT")
    elif requested_status == "low_stock":
        parts.append(f"{requested} is in stock, but only {requested_qty} left")
    elif requested_status == "in_stock":
        parts.append(f"{requested} is in stock: {requested_qty} left")
    parts.append("in stock: " + (", ".join(label(s) for s in sizes if s.quantity > 0) or "none"))
    if sold_out:
        parts.append("sold out: " + ", ".join(sold_out))

    return StockReport(
        product_id=p["product_id"],
        name=p["name"],
        price=p["price"],
        requested_size=requested,
        requested_size_status=requested_status,
        requested_size_quantity=requested_qty,
        sizes=sizes,
        sizes_in_stock=in_stock,
        sizes_sold_out=sold_out,
        total_stock=p["total_stock"],
        summary="; ".join(parts) + ".",
    )


def shop_overview(ctx: RunContext[ShopDeps]) -> ShopOverview:
    """Summary of the whole catalogue: categories with counts and price ranges, every color we carry, and sizes.

    Use for broad questions ("what do you sell?", "what colors do you have?", "what's cheapest?").
    """
    with db.connect() as conn:
        products = db.all_products(conn)

    groups: dict[str, list[float]] = {}
    colors: set[str] = set()
    for p in products:
        groups.setdefault(category_of(p["garment_type"]), []).append(p["price"])
        colors.update(c.lower() for c in p["colors"])

    categories = [
        CategorySummary(category=c, product_count=len(prices), min_price=min(prices), max_price=max(prices))
        for c, prices in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    ]
    if ctx is not None:
        ctx.deps.facts.prices.update(float(x) for c in categories for x in (c.min_price, c.max_price))
        ctx.deps.facts.quantities.update([len(products), *(c.product_count for c in categories)])
    return ShopOverview(
        total_products=len(products),
        categories=categories,
        colors_available=sorted(colors),
        sizes=db.SIZE_ORDER,
    )


def get_my_account(ctx: RunContext[ShopDeps]) -> AccountInfo:
    """The logged-in shopper's own account details: first and last name, email, member-since date,
    and how many chat messages are saved. Use when they ask "what's my email?", "who am I logged in as?",
    or "do you remember me?". Returns logged_in=false for guests.
    """
    if ctx.deps.customer is None or ctx.deps.customer_id is None:
        return AccountInfo(logged_in=False, note="The shopper is a guest. Suggest logging in to save chat history.")
    return AccountInfo(
        logged_in=True,
        customer=ctx.deps.customer,
        saved_messages=memory.count_messages(ctx.deps.customer_id),
    )


def recall_previous_products(ctx: RunContext[ShopDeps], limit: int = 8) -> ChatMemory:
    """Products this shopper was shown in earlier chats (even sessions ago), most recent first,
    with today's price and stock. Use for "what was that hoodie you showed me?" or "anything from last time?".

    Args:
        limit: How many products to return (1-10).
    """
    if ctx.deps.customer_id is None:
        return ChatMemory(logged_in=False, note="Guests have no saved history. Suggest logging in.")
    # The shopper comes from the session (deps), never from model arguments, so the
    # agent can only ever read the current shopper's own memory.
    shown = memory.previously_shown(ctx.deps.customer_id, max(1, min(limit, 10)))
    with db.connect() as conn:
        products = {p["product_id"]: p for p in db.get_products(conn, [pid for pid, _ in shown])}
    remembered = []
    for pid, when in shown:
        if pid in products:
            _record(ctx, products[pid])
            p = products[pid]
            remembered.append(RememberedProduct(
                product_id=pid, name=p["name"], price=p["price"], total_stock=p["total_stock"], last_shown=when,
            ))
    note = None if remembered else "No products have been shown to this shopper in past chats yet."
    return ChatMemory(logged_in=True, products=remembered, note=note)


TOOLS = [search_products, get_product_info, check_stock, shop_overview, get_my_account, recall_previous_products]
