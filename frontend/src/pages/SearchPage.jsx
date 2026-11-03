import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useVoiceInput, voiceShortcutLabel } from '../hooks/useVoiceInput'
import { useSpeech } from '../hooks/useSpeech'
import { parseCommand } from '../voiceCommands'
import { useSettings, format } from '../i18n'
import { API_BASE } from '../api'

const LAST_SEARCH = 'shopsense-last-search'

function StarRating({ rating, count }) {
  const full = Math.round(rating)
  return (
    <p className="product-card__rating">
      <span aria-hidden="true">{'★'.repeat(full) + '☆'.repeat(5 - full)}</span>
      {' '}{rating.toFixed(1)} ({count.toLocaleString()})
    </p>
  )
}

function Price({ price, t }) {
  return (
    <p className="product-card__price">
      {price == null ? t.noPrice : `$${price.toFixed(2)}`}
    </p>
  )
}

function readLastSearch() {
  const raw = sessionStorage.getItem(LAST_SEARCH)
  return raw ? JSON.parse(raw) : null
}

export default function SearchPage() {
  const { lang, autoRead, t } = useSettings()
  const navigate = useNavigate()
  const { speak, stop } = useSpeech(t.speechLang)

  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [query, setQuery] = useState(() => readLastSearch()?.query ?? '')
  const [search, setSearch] = useState(readLastSearch)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState(null)
  const [status, setStatus] = useState('')

  const inputRef = useRef(null)
  const resultsHeadingRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/products`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(data => { setProducts(data); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [])

  async function runSearch(text, viaVoice) {
    const q = text.trim()
    if (!q || searching) return
    setSearching(true)
    setSearchError(null)
    setStatus(t.searching)
    try {
      const res = await fetch(`${API_BASE}/api/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, lang }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
      const data = await res.json()
      setSearch(data)
      sessionStorage.setItem(LAST_SEARCH, JSON.stringify(data))
      setStatus('')
      if (viaVoice || autoRead) speak(data.speech, 'search')
    } catch (err) {
      setSearchError(err.message)
      setStatus(t.errorPrefix + err.message)
    } finally {
      setSearching(false)
    }
  }

  // Focus the results heading once it exists (first search of the visit).
  useEffect(() => {
    if (search && !searching) resultsHeadingRef.current?.focus()
  }, [search, searching])

  function clearSearch() {
    stop()
    setSearch(null)
    setQuery('')
    sessionStorage.removeItem(LAST_SEARCH)
    inputRef.current?.focus()
  }

  function handleVoice(transcript) {
    setStatus(format(t.heard, { t: transcript }))
    const cmd = parseCommand(transcript)
    if (cmd?.type === 'open') {
      const hit = search?.results[cmd.n - 1]
      if (hit) navigate(`/product/${hit.asin}`)
      else speak(format(t.noCommand, { n: cmd.n }), 'command')
      return
    }
    if (cmd?.type === 'stop') { stop(); return }
    if (cmd?.type === 'back') { clearSearch(); return }
    if (cmd?.type === 'repeat') {
      if (search) speak(search.speech, 'search')
      return
    }
    setQuery(transcript)
    runSearch(transcript, true)
  }

  const { listening, start: startVoice, supported: voiceSupported } = useVoiceInput({
    lang: t.speechLang,
    onResult: handleVoice,
    onStart: () => { stop(); setStatus(t.listening) },
    globalShortcut: true,
  })

  const key = voiceShortcutLabel()

  return (
    <main id="main-content" className="page">
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {status}
      </div>

      <div className="search-hero">
        <h1 className="search-hero__title">{t.heroTitle}</h1>
        <p className="search-hero__sub">{format(t.heroSub, { key })}</p>

        <form
          className="search-box"
          role="search"
          onSubmit={e => { e.preventDefault(); runSearch(query, false) }}
        >
          <label htmlFor="need-search" className="sr-only">{t.searchLabel}</label>
          <div className="search-box__inner">
            <svg className="search-box__icon" width="18" height="18" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              ref={inputRef}
              id="need-search"
              type="search"
              className="search-box__input"
              placeholder={t.searchPlaceholder}
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoComplete="off"
              aria-describedby="voice-help-search"
              disabled={searching}
            />
            {voiceSupported && (
              <button
                className={`voice-btn${listening ? ' voice-btn--active' : ''}`}
                onClick={startVoice}
                aria-label={listening ? t.stopListening : format(t.voice, { key })}
                aria-pressed={listening}
                type="button"
              >
                <MicIcon listening={listening} />
              </button>
            )}
            <button type="submit" className="search-box__submit" disabled={searching || !query.trim()}>
              {t.searchBtn}
            </button>
          </div>
          <p id="voice-help-search" className="search-box__help">{t.voiceHelpSearch}</p>
        </form>
      </div>

      {searching && (
        <p className="chat-loading" aria-hidden="true">
          <span>⏳</span> <span>{t.searching}</span>
        </p>
      )}

      {searchError && (
        <div className="empty-state" role="alert">{t.errorPrefix}{searchError}</div>
      )}

      {search && (
        <section className="recs" aria-labelledby="recs-title">
          <div className="recs__head">
            <h2 id="recs-title" className="recs__title" tabIndex={-1} ref={resultsHeadingRef}>
              {t.recTitle}{t.colon}<span lang={/[一-鿿]/.test(search.query) ? 'zh-CN' : 'en'}>{search.query}</span>
            </h2>
            <button type="button" className="quick-btn" onClick={clearSearch}>{t.showAll}</button>
          </div>
          <ol className="recs__list">
            {search.results.map(r => (
              <li key={r.asin} className="rec">
                {r.image_url && <img src={r.image_url} alt="" className="rec__image" loading="lazy" />}
                <div className="rec__body">
                  <h3 className="rec__name">
                    <span className="rec__rank" aria-hidden="true">{r.rank}</span>
                    <Link to={`/product/${r.asin}`}>
                      <span className="sr-only">{r.rank}. </span>
                      <span lang="en">{r.name}</span>
                    </Link>
                  </h3>
                  <p className="rec__reason"><strong>{t.why}{t.colon}</strong>{r.reason}</p>
                  <details className="evidence">
                    <summary>{format(t.evidenceN, { n: r.evidence.length })}</summary>
                    <ul>
                      {r.evidence.map(e => (
                        <li key={e.review_id}>
                          <span className="evidence__stars">{format(t.stars, { r: e.rating })}</span>{' '}
                          <q lang="en">{e.text}</q>
                        </li>
                      ))}
                    </ul>
                  </details>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      <section aria-labelledby="all-title">
        <h2 id="all-title" className="results-count">
          {t.allTitle} · {format(t.nProducts, { n: products.length })}
        </h2>

        {loading && <p aria-busy="true">{t.loading}</p>}
        {error && <div className="empty-state" role="alert">{format(t.loadFailed, { e: error })}</div>}

        {!loading && !error && (
          <ul id="product-grid" className="product-grid">
            {products.map(product => (
              <li key={product.asin}>
                <article className="product-card">
                  <Link to={`/product/${product.asin}`} className="product-card__link">
                    <div className="product-card__image-wrap">
                      <img src={product.image_url} alt="" className="product-card__image" loading="lazy" />
                      <span className="product-card__category" lang="en">{product.category}</span>
                    </div>
                    <div className="product-card__body">
                      <p className="product-card__brand" lang="en">{product.brand}</p>
                      <h3 className="product-card__name" lang="en">{product.name}</h3>
                      <StarRating rating={product.rating} count={product.review_count} />
                      <Price price={product.price} t={t} />
                    </div>
                  </Link>
                </article>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}

export function MicIcon({ listening }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {listening ? (
        <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />
      ) : (
        <>
          <rect x="9" y="2" width="6" height="12" rx="3" />
          <path d="M5 10a7 7 0 0 0 14 0" />
          <line x1="12" y1="17" x2="12" y2="22" />
          <line x1="9" y1="22" x2="15" y2="22" />
        </>
      )}
    </svg>
  )
}
