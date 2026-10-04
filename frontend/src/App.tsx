import { useEffect, type ReactNode } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import ChatResultsPanel from './components/ChatResultsPanel'
import ChatWidget from './components/ChatWidget'
import Footer from './components/Footer'
import NavBar from './components/NavBar'
import About from './pages/About'
import Home from './pages/Home'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'
import Signup from './pages/Signup'

// Start each new page at the top (e.g. after clicking a card far down a grid).
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

// Each page fades/slides in (re-keyed by path).
function RouteFade({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return (
    <div key={pathname} className="route-fade">
      {children}
    </div>
  )
}

function App() {
  return (
    <div className="app">
      <ScrollToTop />
      <NavBar />
      <main className="page">
        <ChatResultsPanel />
        <RouteFade>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        </RouteFade>
      </main>
      <Footer />
      <ChatWidget />
    </div>
  )
}

export default App
