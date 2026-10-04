import type { CSSProperties, MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, GOING_FAST, LOW_STOCK, type Product } from '../api'

interface Props {
  product: Product
  highlightSize?: string | null // e.g. the size a chat search or filter asked for
  index?: number // position in the grid, for the staggered entrance
}

// Gentle 3D tilt that follows the cursor, like picking a shirt up off the table.
function tilt(e: MouseEvent<HTMLAnchorElement>) {
  const el = e.currentTarget
  const r = el.getBoundingClientRect()
  el.style.setProperty('--ry', `${((e.clientX - r.left) / r.width - 0.5) * 8}deg`)
  el.style.setProperty('--rx', `${((e.clientY - r.top) / r.height - 0.5) * -8}deg`)
}
function untilt(e: MouseEvent<HTMLAnchorElement>) {
  e.currentTarget.style.setProperty('--rx', '0deg')
  e.currentTarget.style.setProperty('--ry', '0deg')
}

export default function ProductCard({ product, highlightSize, index = 0 }: Props) {
  const wanted = highlightSize ? product.inventory.find((s) => s.size === highlightSize) : undefined
  let badge: string | null = null
  if (product.total_stock === 0) badge = 'Sold out'
  else if (wanted && wanted.quantity > 0 && wanted.quantity <= LOW_STOCK) badge = `Only ${wanted.quantity} left in ${wanted.size}`
  else if (product.total_stock <= GOING_FAST) badge = 'Going fast'

  return (
    <Link
      to={`/products/${product.product_id}`}
      className="product-card"
      style={{ '--i': Math.min(index, 12) } as CSSProperties}
      onMouseMove={tilt}
      onMouseLeave={untilt}
    >
      <div className="product-card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
        <span className="hang-tag">{formatPrice(product.price).replace('.00', '')}</span>
        {badge && <span className={`card-badge ${product.total_stock === 0 ? 'is-out' : ''}`}>{badge}</span>}
      </div>
      <div className="product-card-body">
        <p className="eyebrow">{product.garment_type}</p>
        <h3>{product.name}</h3>
        <p className="product-card-desc">{product.description}</p>
        <ul className="card-sizes" aria-label="Sizes">
          {product.inventory.map((s) => (
            <li
              key={s.size}
              className={[s.quantity === 0 ? 'out' : '', s.size === highlightSize ? 'hl' : ''].join(' ').trim() || undefined}
              title={s.quantity === 0 ? `${s.size}: sold out` : `${s.size}: ${s.quantity} in stock`}
            >
              {s.size}
            </li>
          ))}
        </ul>
        <span className="card-cta">View details →</span>
      </div>
    </Link>
  )
}
