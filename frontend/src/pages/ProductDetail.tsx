import { useEffect, useState, type MouseEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, fetchProduct, fetchProducts, formatPrice, LOW_STOCK, type Product } from '../api'
import { OPEN_CHAT_EVENT } from '../components/ChatWidget'
import ProductCard from '../components/ProductCard'

function stockLabel(quantity: number): string {
  if (quantity === 0) return 'Sold out'
  if (quantity <= LOW_STOCK) return `Only ${quantity} left`
  return `${quantity} in stock`
}

// Approximate swatch colors for the catalogue's color names (display only).
const SWATCHES: [string, string][] = [
  ['navy', '#1b2a4a'], ['royal', '#2c4fc4'], ['light blue', '#8fb8e8'], ['blue', '#2f5fb3'],
  ['charcoal', '#3b3d42'], ['heather', '#8d9096'], ['gray', '#9a9ca1'], ['black', '#111'],
  ['white', '#f4f4f4'], ['ivory', '#f3eddc'], ['cream', '#efe6cf'], ['red', '#c8283b'],
  ['coral', '#e98a7a'], ['green', '#2f7a4a'], ['gold', '#c9a23a'], ['yellow', '#e9c93b'],
]
function swatch(name: string): string {
  const n = name.toLowerCase()
  if (n.includes('multi')) return 'conic-gradient(#c8283b, #e9c93b, #2f7a4a, #2f5fb3, #c8283b)'
  return SWATCHES.find(([k]) => n.includes(k))?.[1] ?? '#777'
}

const CATEGORY_LABEL: Record<string, string> = {
  hoodie: 'Hoodies', sweatshirt: 'Crewnecks & sweatshirts', 't-shirt': 'T-shirts',
  'quarter-zip': 'Quarter-zips', jacket: 'Jackets', 'long-sleeve': 'Long sleeve',
}

// Zoom follows the cursor, so shoppers can inspect prints and stitching.
function zoomMove(e: MouseEvent<HTMLDivElement>) {
  const r = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--zx', `${((e.clientX - r.left) / r.width) * 100}%`)
  e.currentTarget.style.setProperty('--zy', `${((e.clientY - r.top) / r.height) * 100}%`)
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // Remember which id the loaded data belongs to, so navigating to another
  // product shows "Loading…" instead of the previous item.
  const [loaded, setLoaded] = useState<{ id: string; product?: Product; error?: string }>({ id: '' })

  useEffect(() => {
    let ignore = false
    fetchProduct(productId)
      .then((product) => !ignore && setLoaded({ id: productId, product }))
      .catch((e: unknown) => {
        if (ignore) return
        const error = e instanceof ApiError && e.status === 404 ? "We couldn't find that product." : "Couldn't load this product."
        setLoaded({ id: productId, error })
      })
    return () => {
      ignore = true
    }
  }, [productId])

  // "You may also like": other items in the same category (loaded once).
  const [catalogue, setCatalogue] = useState<Product[]>([])
  useEffect(() => {
    fetchProducts().then(setCatalogue).catch(() => setCatalogue([]))
  }, [])

  const current = loaded.id === productId ? loaded : null
  const product = current?.product
  const error = current?.error

  if (error) {
    return (
      <div className="empty">
        <p className="error">{error}</p>
        <Link to="/products" className="btn">
          Back to products
        </Link>
      </div>
    )
  }
  if (!product) return <p className="muted">Loading…</p>

  const inventory = product.inventory
  const related = catalogue
    .filter((p) => p.category === product.category && p.product_id !== product.product_id && p.total_stock > 0)
    .slice(0, 4)

  return (
    <>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link to="/">Home</Link>
        <span>/</span>
        <Link to="/products">Products</Link>
        <span>/</span>
        <Link to={`/products?category=${product.category}`}>{CATEGORY_LABEL[product.category] ?? 'More'}</Link>
        <span>/</span>
        <span aria-current="page">{product.name}</span>
      </nav>
      <div className="detail">
        <div className="detail-image" onMouseMove={zoomMove}>
          <img src={product.image_url} alt={product.name} />
          <span className="zoom-hint">Hover to zoom</span>
        </div>

        <div className="detail-info">
          <p className="eyebrow">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="detail-price">
            <span className="hang-tag hang-tag-lg">{formatPrice(product.price)}</span>
          </p>
          <p className="detail-desc">{product.description}</p>

          <h2>Colors</h2>
          <ul className="chips swatches">
            {product.colors.map((c) => (
              <li key={c}>
                <i style={{ background: swatch(c) }} aria-hidden="true" />
                {c}
              </li>
            ))}
          </ul>

          <h2>Sizes & stock</h2>
          <ul className="sizes">
            {inventory.map((s) => (
              <li
                key={s.size}
                className={s.quantity === 0 ? 'sold-out' : s.quantity <= LOW_STOCK ? 'low' : ''}
              >
                <strong>{s.size}</strong>
                <span>{stockLabel(s.quantity)}</span>
              </li>
            ))}
          </ul>
          <p className="muted">
            {product.total_stock > 0
              ? `${product.total_stock} units available across all sizes.`
              : 'This item is currently sold out in every size.'}
          </p>

          <ul className="trust-row">
            <li>
              <b>✓</b> Officially licensed
            </li>
            <li>
              <b>●</b> Live stock from our New Haven shop
            </li>
            <li>
              <b>✦</b> 57 Broadway, New Haven
            </li>
          </ul>

          <div className="ask-box">
            <div>
              <strong>Questions about this item?</strong>
              <span>Our assistant knows its live stock: ask about sizes, colors, or similar styles.</span>
            </div>
            <button className="btn" onClick={() => window.dispatchEvent(new Event(OPEN_CHAT_EVENT))}>
              Ask about this item
            </button>
          </div>
        </div>
      </div>

      {related.length > 0 && (
        <section className="home-section related">
          <div className="section-head">
            <div>
              <p className="eyebrow">You may also like</p>
              <h2>More {CATEGORY_LABEL[product.category]?.toLowerCase() ?? 'styles'}</h2>
            </div>
            <Link to={`/products?category=${product.category}`} className="link-arrow">
              See all →
            </Link>
          </div>
          <div className="product-grid">
            {related.map((p, i) => (
              <ProductCard key={p.product_id} product={p} index={i} />
            ))}
          </div>
        </section>
      )}
    </>
  )
}
