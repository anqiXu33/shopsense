import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import DetailPage from './pages/DetailPage'

const THEMES = [
  { id: 'light',        label: '☀️ Light',        ariaLabel: 'Switch to light theme' },
  { id: 'dark',         label: '🌙 Dark',          ariaLabel: 'Switch to dark theme' },
  { id: 'high-contrast',label: '◐ High Contrast',  ariaLabel: 'Switch to high contrast theme' },
]

function Header({ theme, setTheme }) {
  return (
    <header className="global-header" role="banner">
      <div className="global-header__inner">
        <a href="/" className="header-logo" aria-label="ShopSense home">
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect width="32" height="32" rx="8" fill="var(--brand)" />
            <path
              d="M8 22L12 10L16 18L20 13L24 22"
              stroke="var(--brand-text)"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="header-logo__text">ShopSense</span>
        </a>

        <div className="theme-switcher" role="group" aria-label="Theme selection">
          {THEMES.map(t => (
            <button
              key={t.id}
              className={`theme-btn${theme === t.id ? ' theme-btn--active' : ''}`}
              onClick={() => setTheme(t.id)}
              aria-pressed={theme === t.id}
              aria-label={t.ariaLabel}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  )
}

export default function App() {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('shopsense-theme') || 'light'
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('shopsense-theme', theme)
  }, [theme])

  return (
    <BrowserRouter>
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <Header theme={theme} setTheme={setTheme} />
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/product/:asin" element={<DetailPage />} />
      </Routes>
    </BrowserRouter>
  )
}
