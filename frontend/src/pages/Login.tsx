import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

export default function Login() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setError('')
    setSubmitting(true)
    try {
      await login(String(data.get('email')), String(data.get('password')))
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Log in failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Log in</h1>
        <p className="muted">Welcome back! Log in to save your chats with our assistant.</p>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" required />
        </label>
        <label>
          Password
          <input type="password" name="password" autoComplete="current-password" required />
        </label>
        <button type="submit" className="btn" disabled={submitting}>
          {submitting ? 'Logging in…' : 'Log in'}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
        <p className="muted">
          New here? <Link to="/signup">Create an account</Link>
        </p>
      </form>
    </div>
  )
}
