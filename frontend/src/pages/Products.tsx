import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import ProductCard from '../components/ProductCard'

const CATEGORIES: [string, string][] = [
  ['hoodie', 'Hoodies'],
  ['sweatshirt', 'Crewnecks & sweatshirts'],
  ['t-shirt', 'T-shirts'],
  ['quarter-zip', 'Quarter-zips'],
  ['jacket', 'Jackets'],
  ['long-sleeve', 'Long sleeve'],
]
const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
const SORTS: [string, string][] = [
  ['name', 'Name (A–Z)'],
  ['price-asc', 'Price: low to high'],
  ['price-desc', 'Price: high to low'],
  ['stock', 'Most in stock'],
]

// Filters live in the URL (?category=hoodie&size=M&sort=price-asc&q=bulldog), so a filtered
// view can be shared, bookmarked, and the browser Back button works.
export default function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [params, setParams] = useSearchParams()

  const query = params.get('q') ?? ''
  const category = params.get('category') ?? ''
  const size = params.get('size') ?? ''
  const sort = params.get('sort') ?? 'name'

  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value && !(key === 'sort' && value === 'name')) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: key === 'q' }) // typing shouldn't flood the history
  }

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setError("Couldn't load products. Is the backend running on port 8000?"))
      .finally(() => setLoading(false))
  }, [])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const p of products) c[p.category] = (c[p.category] ?? 0) + 1
    return c
  }, [products])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = products.filter(
      (p) =>
        (!category || p.category === category) &&
        (!size || p.inventory.some((s) => s.size === size && s.quantity > 0)) &&
        (!q ||
          [p.name, p.garment_type, p.description, ...p.colors, ...p.search_tags].join(' ').toLowerCase().includes(q)),
    )
    const sorted = [...list]
    if (sort === 'price-asc') sorted.sort((a, b) => a.price - b.price || a.name.localeCompare(b.name))
    else if (sort === 'price-desc') sorted.sort((a, b) => b.price - a.price || a.name.localeCompare(b.name))
    else if (sort === 'stock') sorted.sort((a, b) => b.total_stock - a.total_stock)
    else sorted.sort((a, b) => a.name.localeCompare(b.name))
    return sorted
  }, [products, query, category, size, sort])

  const filtered = Boolean(query || category || size)

  return (
    <>
      <div className="section-head">
        <div>
          <p className="eyebrow">Shop</p>
          <h1>All products</h1>
        </div>
        <input
          className="search"
          type="search"
          placeholder="Search hoodies, bulldog, navy…"
          value={query}
          onChange={(e) => update('q', e.target.value)}
          aria-label="Search products"
        />
      </div>

      <div className="filters">
        <div className="filter-chips" role="group" aria-label="Category">
          <button className={!category ? 'active' : ''} onClick={() => update('category', '')}>
            All <span>{products.length}</span>
          </button>
          {CATEGORIES.filter(([key]) => counts[key]).map(([key, label]) => (
            <button key={key} className={category === key ? 'active' : ''} onClick={() => update('category', key)}>
              {label} <span>{counts[key]}</span>
            </button>
          ))}
        </div>
        <div className="filter-row">
          <label>
            In stock in
            <select value={size} onChange={(e) => update('size', e.target.value)}>
              <option value="">Any size</option>
              {SIZES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sort by
            <select value={sort} onChange={(e) => update('sort', e.target.value)}>
              {SORTS.map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {filtered && (
            <button className="btn btn-small btn-ghost" onClick={() => setParams(new URLSearchParams())}>
              Clear filters
            </button>
          )}
        </div>
      </div>

      {loading && <p className="muted">Loading products…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && (
        <p className="muted">
          Showing {visible.length} of {products.length} items
          {size && ` · in stock in ${size}`}
        </p>
      )}

      {!loading && !error && visible.length === 0 && (
        <div className="empty-results">
          <p>No products match these filters.</p>
          <button className="btn btn-small" onClick={() => setParams(new URLSearchParams())}>
            Clear filters
          </button>
        </div>
      )}

      <div className="product-grid">
        {visible.map((p, i) => (
          <ProductCard key={p.product_id} product={p} highlightSize={size || null} index={i} />
        ))}
      </div>
    </>
  )
}
