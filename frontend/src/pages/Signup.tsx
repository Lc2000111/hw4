import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'

const MIN_PASSWORD = 8

export default function Signup() {
  const { user, signup } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const field = (name: string) => String(data.get(name) ?? '')
    const password = field('password')
    const confirm = field('confirm_password')

    // Quick checks in the browser; the backend checks everything again.
    if (password.length < MIN_PASSWORD || confirm.length < MIN_PASSWORD) {
      setError(`Password must be at least ${MIN_PASSWORD} characters.`)
      return
    }
    if (password !== confirm) {
      setError("Passwords don't match.")
      return
    }

    setError('')
    setSubmitting(true)
    try {
      await signup({
        first_name: field('first_name'),
        last_name: field('last_name'),
        email: field('email'),
        password,
        confirm_password: confirm,
      })
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-up failed.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth">
      <form className="auth-card" onSubmit={handleSubmit}>
        <h1>Create account</h1>
        <p className="muted">Join Campus Customs to keep your chat history and favorites.</p>
        <div className="auth-row">
          <label>
            First name
            <input name="first_name" autoComplete="given-name" maxLength={50} required />
          </label>
          <label>
            Last name
            <input name="last_name" autoComplete="family-name" maxLength={50} required />
          </label>
        </div>
        <label>
          Email
          <input type="email" name="email" autoComplete="email" required />
        </label>
        <label>
          <span>
            Password <span className="hint">(at least {MIN_PASSWORD} characters)</span>
          </span>
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD}
            maxLength={128}
            required
          />
        </label>
        <label>
          Confirm password
          <input
            type="password"
            name="confirm_password"
            autoComplete="new-password"
            minLength={MIN_PASSWORD}
            maxLength={128}
            required
          />
        </label>
        <button type="submit" className="btn" disabled={submitting}>
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
        <p className="muted">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </form>
    </div>
  )
}
