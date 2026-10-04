import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../useAuth'
import Patch from './Patch'
import Ticker from './Ticker'

const links = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

export default function NavBar() {
  const { user, ready, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="nav-wrap">
      <header className="navbar">
        <Link to="/" className="brand" aria-label="Campus Customs home">
          <Patch size={38} />
          <span className="brand-word">
            Campus <span>Customs</span>
          </span>
        </Link>
        <nav className="nav-links">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="nav-account">
          {!ready ? null : user ? (
            <>
              <span className="nav-greeting">Hi, {user.first_name}</span>
              <button className="btn btn-small btn-ghost" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <NavLink to="/signup" className="btn btn-small">
                Create account
              </NavLink>
            </>
          )}
        </div>
      </header>
      <Ticker />
    </div>
  )
}
