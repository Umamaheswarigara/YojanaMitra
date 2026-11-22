import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import { apiLogout, getStoredUser, request } from './api'
import { SchemeDetails } from './components'
import { AboutPage, AssistantPage, DocumentsPage, EligibilityPage, HomePage, SchemesPage } from './pages'
import { AuthPage } from './AuthPage'
import { copy } from './translations'

const pageLinks = [
  { path: '/', key: 'home', label: 'Home' },
  { path: '/schemes', key: 'all', label: 'Explore Schemes' },
  { path: '/eligibility', key: 'eligible', label: 'Eligibility Checker' },
  { path: '/assistant', key: 'assistant', label: 'AI Assistant' },
  { path: '/documents', key: 'docs', label: 'Document Explainer' },
  { path: '/about', key: 'about', label: 'About' },
]

function RouteLink({ href, navigate, children, ...props }) {
  return <a href={href} {...props} onClick={event => {
    props.onClick?.(event)
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    navigate(href)
  }}>{children}</a>
}

function readLocation() {
  return { pathname: window.location.pathname, search: window.location.search }
}

// ── User menu ─────────────────────────────────────────────────────────────────
function UserMenu({ user, onSignOut }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function close(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const initials = (user.name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="user-menu-wrap" ref={ref}>
      <button
        className="user-menu-btn"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label="User account menu"
      >
        <span className="user-avatar" aria-hidden="true">{initials}</span>
        <span>{user.name.split(' ')[0]}</span>
        <span aria-hidden="true" style={{fontSize:'10px', opacity:0.7}}>{open ? '▲' : '▾'}</span>
      </button>
      {open && (
        <div className="user-dropdown" role="menu">
          <div className="user-dropdown-name">{user.name}</div>
          <div className="user-dropdown-email">{user.email}</div>
          <button
            role="menuitem"
            className="user-dropdown-btn user-dropdown-btn--danger"
            onClick={() => { setOpen(false); onSignOut() }}
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────
function App() {
  const [location, setLocation] = useState(readLocation)
  const [lang, setLang] = useState(() => window.localStorage.getItem('ym-language') || 'en')
  const [menuOpen, setMenuOpen] = useState(false)
  const [selectedScheme, setSelectedScheme] = useState(null)
  const [detailError, setDetailError] = useState('')
  const [user, setUser] = useState(() => getStoredUser())
  const [showAuth, setShowAuth] = useState(false)

  const t = { ...copy[lang], lang }
  const currentPath = location.pathname.replace(/\/$/, '') || '/'

  useEffect(() => {
    const update = () => { setLocation(readLocation()); setMenuOpen(false) }
    window.addEventListener('popstate', update)
    return () => window.removeEventListener('popstate', update)
  }, [])

  useEffect(() => {
    const titles = {
      '/': 'YojanaMitra — Government Schemes Made Simple',
      '/schemes': 'Explore Schemes | YojanaMitra',
      '/eligibility': 'Eligibility Checker | YojanaMitra',
      '/assistant': 'AI Assistant | YojanaMitra',
      '/documents': 'Document Explainer | YojanaMitra',
      '/about': 'About | YojanaMitra',
    }
    document.title = titles[currentPath] || 'YojanaMitra'
  }, [currentPath])

  useEffect(() => {
    window.localStorage.setItem('ym-language', lang)
    document.documentElement.lang = lang
  }, [lang])

  function navigate(href) {
    const target = new URL(href, window.location.origin)
    window.history.pushState({}, '', `${target.pathname}${target.search}${target.hash}`)
    setLocation(readLocation())
    setMenuOpen(false)
    setSelectedScheme(null)
    setDetailError('')
    setShowAuth(false)
    window.scrollTo({ top: 0, behavior: 'auto' })
  }

  function handleAuthSuccess(newUser) {
    setUser(newUser)
    setShowAuth(false)
  }

  function handleSignOut() {
    apiLogout()
    setUser(null)
  }

  async function selectScheme(scheme) {
    setDetailError('')
    try { setSelectedScheme(await request(`/schemes/${encodeURIComponent(scheme.id)}`, {}, lang)) }
    catch (error) { setSelectedScheme(scheme); setDetailError(error.message || t.retry) }
  }

  const page = showAuth
    ? <AuthPage onSuccess={handleAuthSuccess} t={t} />
    : currentPath === '/' ? <HomePage t={t} lang={lang} navigate={navigate} onSelectScheme={selectScheme} />
    : currentPath === '/schemes' ? <SchemesPage key={`${currentPath}${location.search}`} t={t} lang={lang} search={location.search} onSelectScheme={selectScheme} />
    : currentPath === '/eligibility' ? <EligibilityPage t={t} lang={lang} navigate={navigate} onSelectScheme={selectScheme} />
    : currentPath === '/assistant' ? <AssistantPage t={t} lang={lang} user={user} />
    : currentPath === '/documents' ? <DocumentsPage t={t} lang={lang} />
    : currentPath === '/about' ? <AboutPage />
    : <section className="page-section content-section"><div className="empty-state"><h1>Page not found</h1><RouteLink href="/" navigate={navigate}>Return home</RouteLink></div></section>

  return (
    <div className="app-shell">
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header className="topbar">
        {/* Brand */}
        <RouteLink className="brand" href="/" navigate={navigate} aria-label="YojanaMitra home">
          <span className="brand-mark">Y</span>
          <span>Yojana<span className="brand-light">Mitra</span></span>
        </RouteLink>

        {/* Hamburger (mobile) */}
        <button
          className="mobile-menu-toggle"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          aria-controls="primary-navigation"
          onClick={() => setMenuOpen(o => !o)}
        >
          <span /><span /><span />
        </button>

        {/* Nav links */}
        <nav
          id="primary-navigation"
          className={`primary-navigation${menuOpen ? ' is-open' : ''}`}
          aria-label="Main navigation"
        >
          {pageLinks.map(link => (
            <RouteLink
              key={link.path}
              href={link.path}
              navigate={navigate}
              aria-current={currentPath === link.path ? 'page' : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {link.key === 'home' || link.key === 'about' ? link.label : t[link.key] || link.label}
            </RouteLink>
          ))}
        </nav>

        {/* Right controls */}
        <div className="topbar-controls">
          <label className="language-control" aria-label="Language">
            <span aria-hidden="true">🌐</span>
            <select
              value={lang}
              onChange={e => setLang(e.target.value)}
              aria-label="Choose language"
            >
              <option value="en">English</option>
              <option value="te">తెలుగు</option>
              <option value="hi">हिन्दी</option>
            </select>
          </label>
          {user
            ? <UserMenu user={user} onSignOut={handleSignOut} />
            : <button className="signin-btn" onClick={() => setShowAuth(true)}>Sign In</button>
          }
        </div>
      </header>

      {/* ── Page content ──────────────────────────────────────────────────── */}
      <main
        key={currentPath + String(showAuth)}
        id="top"
        className={`route-content route-${currentPath === '/' ? 'home' : currentPath.slice(1)}`}
      >
        {page}
      </main>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="site-footer">
        <RouteLink className="brand" href="/" navigate={navigate}>
          <span className="brand-mark">Y</span>
          <span>Yojana<span className="brand-light">Mitra</span></span>
        </RouteLink>
        <span>|</span>
        <span>{t.powered || 'Government scheme information, made clear'}</span>
        <span style={{ marginLeft: 'auto' }}>© 2026 YojanaMitra</span>
      </footer>

      {/* ── Toasts & overlays ─────────────────────────────────────────── */}
      {detailError && <div className="detail-error" role="status">{detailError}</div>}
      <SchemeDetails scheme={selectedScheme} lang={lang} labels={t} onClose={() => setSelectedScheme(null)} />
    </div>
  )
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode><App /></React.StrictMode>
)
