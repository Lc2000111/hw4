"""Shared database access for the API (main.py) and the agent's tools (tools.py).

Product data is only ever read through these helpers, so the website and the
chatbot always show the same prices and stock.
"""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the hw4 folder
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "campus_customs.db"
PRODUCTS_DIR = DATA_DIR / "products"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]
LOW_STOCK = 5  # "only N left" at or below this


def connect() -> sqlite3.Connection:
    """Open the database read-only, for product lookups (website and agent)."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_rw() -> sqlite3.Connection:
    """Open the database for writing (accounts and sessions only)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def product_from_row(row: sqlite3.Row) -> dict:
    """Turn a catalogue row into JSON: parse list fields and add an image URL."""
    product = dict(row)
    product["colors"] = json.loads(product["colors"])
    product["search_tags"] = json.loads(product["search_tags"])
    product["image_url"] = f"/media/{product['image_file_path']}"
    product["category"] = category_of(product["garment_type"])
    return product


def _size_key(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)


def inventory_for(conn: sqlite3.Connection, product_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
    ).fetchall()
    return sorted((dict(r) for r in rows), key=lambda s: _size_key(s["size"]))


def get_product(conn: sqlite3.Connection, product_id: str) -> dict | None:
    """One product with per-size stock and total stock, or None if unknown."""
    row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
    if row is None:
        return None
    product = product_from_row(row)
    product["inventory"] = inventory_for(conn, product_id)
    product["total_stock"] = sum(s["quantity"] for s in product["inventory"])
    return product


def all_products(conn: sqlite3.Connection) -> list[dict]:
    """Every product with per-size stock, sorted by name (102 rows, so this is cheap)."""
    stock: dict[str, list[dict]] = {}
    for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
        stock.setdefault(r["product_id"], []).append({"size": r["size"], "quantity": r["quantity"]})

    products = []
    for row in conn.execute("SELECT * FROM catalogue ORDER BY name"):
        product = product_from_row(row)
        product["inventory"] = sorted(stock.get(product["product_id"], []), key=lambda s: _size_key(s["size"]))
        product["total_stock"] = sum(s["quantity"] for s in product["inventory"])
        products.append(product)
    return products


def get_products(conn: sqlite3.Connection, product_ids: list[str]) -> list[dict]:
    """Several products by id, in the given order; duplicates and unknown ids are skipped."""
    products, seen = [], set()
    for pid in product_ids:
        if pid in seen:
            continue
        seen.add(pid)
        product = get_product(conn, pid)
        if product is not None:
            products.append(product)
    return products


def category_of(garment_type: str) -> str:
    """Map the catalogue's 22 garment_type spellings to one broad category."""
    g = garment_type.lower()
    if "quarter-zip" in g:
        return "quarter-zip"
    if "jacket" in g:
        return "jacket"
    if "hood" in g:
        return "hoodie"
    if "t-shirt" in g:
        return "t-shirt"
    if "long-sleeve" in g:
        return "long-sleeve"
    if "crewneck" in g or "mockneck" in g or "sweatshirt" in g:
        return "sweatshirt"
    return "other"
