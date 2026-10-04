import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { fetchProducts, formatPrice, GOING_FAST, type Product } from '../api'
import { OPEN_CHAT_EVENT } from '../components/ChatWidget'
import ProductCard from '../components/ProductCard'

// Hand-picked hero and favorite items.
const HERO_IDS = ['basic-hoodie-big-yale', '2025-yale-vs-harvard-t-shirt', 'district-vit-crewneck-vintage-bulldog']
const FEATURED_IDS = [
  '2025-yale-vs-harvard-t-shirt',
  'basic-hoodie-big-yale',
  'district-vit-crewneck-vintage-bulldog',
  'brooks-brothers-bomber-jacket-yale',
]
const CATEGORIES: [string, string, string][] = [
  ['hoodie', 'Hoodies', 'basic-hoodie-big-yale'],
  ['sweatshirt', 'Crewnecks', 'district-vit-crewneck-vintage-bulldog'],
  ['t-shirt', 'Tees', 'boola-boola-t-shirt'],
  ['quarter-zip', 'Quarter-zips', 'branford-1-4-zip'],
  ['jacket', 'Jackets', 'brooks-brothers-bomber-jacket-yale'],
]

export default function Home() {
  const [products, setProducts] = useState<Product[]>([])

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setProducts([]))
  }, [])

  const byId = useMemo(() => new Map(products.map((p) => [p.product_id, p])), [products])
  const pick = (ids: string[]) => ids.map((id) => byId.get(id)).filter((p): p is Product => !!p)
  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const p of products) c[p.category] = (c[p.category] ?? 0) + 1
    return c
  }, [products])
  // Real scarcity only: the items with the fewest units left right now.
  const goingFast = useMemo(
    () => products.filter((p) => p.total_stock > 0 && p.total_stock <= GOING_FAST).sort((a, b) => a.total_stock - b.total_stock).slice(0, 8),
    [products],
  )

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">57 Broadway · New Haven, CT</p>
          <h1>
            <span className="hero-small">Wear your</span>
            <span className="varsity" data-text="BULLDOG">
              BULLDOG
            </span>
            <span className="hero-small">
              pride<em>.</em>
            </span>
          </h1>
          <p className="hero-sub">
            Officially licensed Yale apparel you'll actually want to wear, from soft everyday tees to heavyweight hoodies
            built for long New Haven winters.
          </p>
          <div className="hero-actions">
            <Link to="/products" className="btn btn-lg">
              Shop the collection
            </Link>
            <button className="btn btn-lg btn-ghost" onClick={() => window.dispatchEvent(new Event(OPEN_CHAT_EVENT))}>
              Ask our assistant
            </button>
          </div>
          <p className="hero-proof">
            <strong>{products.length || 102}</strong> styles · sizes <strong>XS–XXL</strong> · stock checked live
          </p>
        </div>

        <div className="hero-collage" aria-hidden="true">
          {pick(HERO_IDS).map((p, i) => (
            <Link key={p.product_id} to={`/products/${p.product_id}`} className={`polaroid polaroid-${i}`} tabIndex={-1}>
              <img src={p.image_url} alt="" />
              <span className="hang-tag">{formatPrice(p.price).replace('.00', '')}</span>
              <span className="polaroid-caption">{p.name}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="home-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">Shop by category</p>
            <h2>Find your fit</h2>
          </div>
          <Link to="/products" className="link-arrow">
            All products →
          </Link>
        </div>
        <div className="category-rail">
          {CATEGORIES.map(([key, label, imageId], i) => {
            const img = byId.get(imageId)
            return (
              <Link key={key} to={`/products?category=${key}`} className="category-tile" style={{ '--i': i } as CSSProperties}>
                {img && <img src={img.image_url} alt="" loading="lazy" />}
                <span className="category-label">{label}</span>
                <span className="category-count">{counts[key] ?? '—'} styles</span>
              </Link>
            )
          })}
        </div>
      </section>

      {goingFast.length > 0 && (
        <section className="home-section">
          <div className="section-head">
            <div>
              <p className="eyebrow eyebrow-live">
                <span className="live-dot" /> Live from the stockroom
              </p>
              <h2>Going fast</h2>
            </div>
            <p className="muted section-note">The styles with the fewest units left right now.</p>
          </div>
          <div className="going-fast">
            {goingFast.map((p) => (
              <Link key={p.product_id} to={`/products/${p.product_id}`} className="fast-item">
                <img src={p.image_url} alt="" loading="lazy" />
                <div>
                  <strong>{p.name}</strong>
                  <span>
                    {formatPrice(p.price)} · <em>{p.total_stock} left</em>
                  </span>
                  <span className="stock-meter" aria-hidden="true">
                    <i style={{ width: `${Math.max(8, (p.total_stock / GOING_FAST) * 100)}%` }} />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="home-section">
        <div className="section-head">
          <div>
            <p className="eyebrow">Fan favorites</p>
            <h2>The classics</h2>
          </div>
          <Link to="/products" className="link-arrow">
            View all →
          </Link>
        </div>
        <div className="product-grid">
          {pick(FEATURED_IDS).map((p, i) => (
            <ProductCard key={p.product_id} product={p} index={i} />
          ))}
        </div>
      </section>

      <section className="pillars">
        <div>
          <span className="pillar-num">01</span>
          <h3>Made for every Eli</h3>
          <p>Students, alumni, parents, and fans. If you love Yale, there's a fit for you.</p>
        </div>
        <div>
          <span className="pillar-num">02</span>
          <h3>College & team colors</h3>
          <p>Show off your residential college, your sport, or the rivalry that matters most.</p>
        </div>
        <div>
          <span className="pillar-num">03</span>
          <h3>Honest answers</h3>
          <p>Ask our chat assistant about any item. It checks real prices and stock for you.</p>
        </div>
      </section>
    </>
  )
}
