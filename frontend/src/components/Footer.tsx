import { Link } from 'react-router-dom'
import Patch from './Patch'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-pennant" aria-hidden="true">
        <span>BOOLA BOOLA</span>
      </div>
      <div className="footer-grid">
        <div className="footer-brand">
          <Patch size={56} />
          <div>
            <p className="brand-word">
              Campus <span>Customs</span>
            </p>
            <p>57 Broadway, New Haven, CT 06511</p>
          </div>
        </div>
        <nav>
          <Link to="/products">Shop all</Link>
          <Link to="/products?category=hoodie">Hoodies</Link>
          <Link to="/products?category=sweatshirt">Crewnecks</Link>
          <Link to="/products?category=t-shirt">Tees</Link>
        </nav>
        <nav>
          <Link to="/about">About Us</Link>
          <Link to="/login">Log in</Link>
          <Link to="/signup">Create account</Link>
        </nav>
      </div>
      <p className="footer-note">Officially licensed Yale apparel · Class project for MGT 409</p>
    </footer>
  )
}
