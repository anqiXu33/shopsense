import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import DetailPage from './pages/DetailPage'

const THEMES = [
  { id: 'light',        label: '☀️ 浅色',   ariaLabel: '切换到浅色主题' },
  { id: 'dark',         label: '🌙 深色',   ariaLabel: '切换到深色主题' },
  { id: 'high-contrast',label: '◐ 高对比度', ariaLabel: '切换到高对比度主题' },
]

function Header({ theme, setTheme }) {
  return (
    <header className="global-header" role="banner">
      <div className="global-header__inner">
        <a href="/" className="header-logo" aria-label="ShopSense 首页">
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

        <div className="theme-switcher" role="group" aria-label="主题选择">
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
      <a href="#main-content" className="skip-link">跳到主内容</a>
      <Header theme={theme} setTheme={setTheme} />
      <Routes>
        <Route path="/" element={<SearchPage />} />
        <Route path="/product/:asin" element={<DetailPage />} />
      </Routes>
    </BrowserRouter>
  )
}
