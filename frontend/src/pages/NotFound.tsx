import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="empty">
      <h1>Page not found</h1>
      <p className="muted">That page wandered off campus.</p>
      <Link to="/" className="btn">
        Go home
      </Link>
    </div>
  )
}
