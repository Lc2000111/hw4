import { formatPrice, type SearchFilters } from '../api'
import { useChatResults } from '../useChatResults'
import ProductCard from './ProductCard'

function filterChips(f: SearchFilters): string[] {
  const chips: string[] = []
  if (f.category) chips.push(f.category)
  if (f.color) chips.push(f.color)
  if (f.size) chips.push(`size ${f.size} in stock`)
  if (f.max_price != null) chips.push(`under ${formatPrice(f.max_price)}`)
  if (f.query) chips.push(`"${f.query}"`)
  return chips
}

// Renders the products the chat assistant found as cards at the top of the page.
// Cards are the same ProductCard used on the Products page, so clicking one opens
// the single-item page exactly like everywhere else.
export default function ChatResultsPanel() {
  const { results, expanded, version, setExpanded, clear } = useChatResults()
  if (!results) return null

  const shown = results.products.length
  const count =
    results.total_matches > shown
      ? `${shown} of ${results.total_matches} items`
      : `${shown} ${shown === 1 ? 'item' : 'items'}`

  return (
    <section
      key={version}
      className={`chat-results ${expanded ? 'is-expanded' : 'is-collapsed'}`}
      aria-label="Products from your chat"
    >
      <header className="chat-results-head">
        <div>
          <p className="eyebrow">From your chat</p>
          <h2>
            {results.title} <span className="muted">· {count}</span>
          </h2>
          {expanded && (
            <ul className="chips chat-results-filters">
              {filterChips(results.filters).map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="chat-results-actions">
          <button className="btn btn-small btn-ghost" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Hide' : 'Show results'}
          </button>
          <button className="chat-results-close" onClick={clear} aria-label="Clear chat results">
            ×
          </button>
        </div>
      </header>

      {expanded && (
        <div className="product-grid">
          {results.products.map((p, i) => (
            <ProductCard key={p.product_id} product={p} highlightSize={results.filters.size} index={i} />
          ))}
        </div>
      )}
    </section>
  )
}
