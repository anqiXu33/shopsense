import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import SearchPage from './pages/SearchPage'
import DetailPage from './pages/DetailPage'
import { SettingsContext, STRINGS, useSettings } from './i18n'

const THEMES = [
  { id: 'light',         label: '☀️ Light',         key: 'themeLight' },
  { id: 'dark',          label: '🌙 Dark',          key: 'themeDark' },
  { id: 'high-contrast', label: '◐ High Contrast', key: 'themeContrast' },
]

function stored(key, initial) {
  return localStorage.getItem(key) ?? initial
}

function Header({ theme, setTheme }) {
  const { lang, setLang, autoRead, setAutoRead, t } = useSettings()
  return (
    <header className="global-header" role="banner">
      <div className="global-header__inner">
        <Link to="/" className="header-logo" aria-label={t.home}>
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
        </Link>

        <div className="header-controls">
          {/* Each button is labelled in its own language, so a speaker of
              either language can find the way back to theirs. */}
          <div className="theme-switcher" role="group" aria-label="语言 / Language">
            {['zh', 'en'].map(l => (
              <button
                key={l}
                type="button"
                lang={l}
                className={`theme-btn${lang === l ? ' theme-btn--active' : ''}`}
                onClick={() => setLang(l)}
                aria-pressed={lang === l}
                aria-label={STRINGS[l].switchLang}
              >
                {STRINGS[l].langName}
              </button>
            ))}
          </div>

          <button
            type="button"
            className={`theme-btn${autoRead ? ' theme-btn--active' : ''}`}
            onClick={() => setAutoRead(!autoRead)}
            aria-pressed={autoRead}
            aria-describedby="auto-read-hint"
          >
            🔊 {t.autoRead}
          </button>
          <p id="auto-read-hint" className="sr-only">{t.autoReadHint}</p>

          <div className="theme-switcher" role="group" aria-label={t.themes}>
            {THEMES.map(th => (
              <button
                key={th.id}
                type="button"
                className={`theme-btn${theme === th.id ? ' theme-btn--active' : ''}`}
                onClick={() => setTheme(th.id)}
                aria-pressed={theme === th.id}
                aria-label={t[th.key]}
              >
                {th.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  )
}

function SkipLink() {
  const { t } = useSettings()
  return <a href="#main-content" className="skip-link">{t.skip}</a>
}

export default function App() {
  const [theme, setTheme] = useState(() => stored('shopsense-theme', 'light'))
  const [lang, setLang] = useState(() => stored('shopsense-lang', 'zh'))
  const [autoRead, setAutoRead] = useState(() => stored('shopsense-page-speech', 'false') === 'true')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('shopsense-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en'
    localStorage.setItem('shopsense-lang', lang)
  }, [lang])

  useEffect(() => {
    localStorage.setItem('shopsense-page-speech', String(autoRead))
  }, [autoRead])

  return (
    <SettingsContext.Provider value={{ lang, setLang, autoRead, setAutoRead }}>
      <BrowserRouter>
        <SkipLink />
        <Header theme={theme} setTheme={setTheme} />
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/product/:asin" element={<DetailPage />} />
        </Routes>
      </BrowserRouter>
    </SettingsContext.Provider>
  )
}
