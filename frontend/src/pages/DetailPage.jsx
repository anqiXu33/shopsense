import { useState, useEffect, useRef } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useVoiceInput, voiceShortcutLabel } from '../hooks/useVoiceInput'
import { useSpeech } from '../hooks/useSpeech'
import { parseCommand } from '../voiceCommands'
import { useSettings, format } from '../i18n'
import { MicIcon } from './SearchPage'
import { API_BASE } from '../api'

function Evidence({ items, t }) {
  if (items.length === 0) return null
  return (
    <details className="evidence">
      <summary>{format(t.sources, { n: items.length })}</summary>
      <ul>
        {items.map(e => (
          <li key={e.review_id}>
            <span className="evidence__stars">{format(t.stars, { r: e.rating })}</span>{' '}
            <q lang="en">{e.text}</q>
          </li>
        ))}
      </ul>
    </details>
  )
}

export default function DetailPage() {
  const { asin } = useParams()
  const navigate = useNavigate()
  const { lang, autoRead, t } = useSettings()
  const { speak, stop, speakingId } = useSpeech(t.speechLang)

  const [product, setProduct] = useState(null)
  const [productError, setProductError] = useState(null)

  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [asking, setAsking] = useState(false)
  const [status, setStatus] = useState('')

  const inputRef = useRef(null)
  const headingRef = useRef(null)
  const chatLogRef = useRef(null)

  // Highlights are rendered server-side in the selected language, so the
  // product is refetched when the language changes.
  useEffect(() => {
    setProduct(null)
    fetch(`${API_BASE}/api/products/${asin}?lang=${lang}`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setProduct)
      .catch(err => setProductError(err.message))
  }, [asin, lang])

  // Feature 1: on opening a product, move focus to its name and read the
  // highlights aloud (unless auto-read is off, e.g. for screen-reader users).
  useEffect(() => {
    if (!product) return
    headingRef.current?.focus()
    if (autoRead) speak(product.highlights.speech, 'highlights')
  }, [product]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (chatLogRef.current) chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight
  }, [messages, asking])

  async function ask(text, viaVoice) {
    const q = text.trim()
    if (!q || asking) return
    stop()
    setQuestion('')
    setAsking(true)
    setStatus(t.thinking)
    setMessages(prev => [...prev, { role: 'user', content: q }])
    try {
      const res = await fetch(`${API_BASE}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asin, question: q, lang }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'ai', content: data.answer, evidence: data.evidence }])
      setStatus('')
      if (viaVoice || autoRead) speak(data.answer, `msg-${messages.length + 1}`)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: t.errorPrefix + err.message, evidence: [] }])
      setStatus(t.errorPrefix + err.message)
    } finally {
      setAsking(false)
      // The input is disabled while asking; focus it once it is enabled again.
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }

  function handleVoice(transcript) {
    setStatus(format(t.heard, { t: transcript }))
    const cmd = parseCommand(transcript)
    if (cmd?.type === 'back') { stop(); navigate('/'); return }
    if (cmd?.type === 'stop') { stop(); return }
    if (cmd?.type === 'repeat') { speak(product.highlights.speech, 'highlights'); return }
    if (cmd?.type === 'describe') { speak(product.appearance, 'appearance'); return }
    ask(transcript, true)
  }

  const { listening, start: startVoice, supported: voiceSupported } = useVoiceInput({
    lang: t.speechLang,
    onResult: handleVoice,
    onStart: () => { stop(); setStatus(t.listening) },
    globalShortcut: true,
  })

  if (productError) {
    return (
      <main id="main-content" className="page-error" role="alert">
        {format(t.loadFailed, { e: productError })}
      </main>
    )
  }
  if (!product) {
    return <main id="main-content" className="page-loading" aria-busy="true">{t.loading}</main>
  }

  const { name, brand, price, image_url, rating, review_count, category, highlights, appearance, n_reviews } = product
  const key = voiceShortcutLabel()
  const readingHighlights = speakingId === 'highlights'
  const readingAppearance = speakingId === 'appearance'

  return (
    <main id="main-content" className="page">
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {status}
      </div>

      <Link to="/" className="back-link" aria-label={t.backLabel}>{t.back}</Link>

      <div className="detail-layout">
        {/* ── Left: product and its review highlights ─────────────── */}
        <div>
          <section className="detail-product" aria-labelledby="product-name">
            <div className="detail-product__image-wrap">
              <img src={image_url} alt="" className="detail-product__image" />
            </div>
            <div className="detail-product__info">
              <h1 id="product-name" className="detail-product__name" lang="en" tabIndex={-1} ref={headingRef}>
                {name}
              </h1>
              <p className="detail-product__field">
                <span className="sr-only">{t.brand}</span><span lang="en">{brand}</span>
              </p>
              <p className="detail-product__price">
                <span className="sr-only">{t.price}</span>
                {price == null ? t.noPrice : `$${price.toFixed(2)}`}
              </p>
              <p className="detail-product__field">
                <span aria-hidden="true">
                  {'★'.repeat(Math.round(rating))}{'☆'.repeat(5 - Math.round(rating))}
                  {' '}{rating.toFixed(1)} · {review_count.toLocaleString()}
                </span>
                <span className="sr-only">
                  {format(t.rating, { r: rating.toFixed(1), n: review_count.toLocaleString() })}
                </span>
              </p>
              <p className="detail-product__field">
                <span className="sr-only">{t.category}</span><span lang="en">{category}</span>
              </p>
            </div>
          </section>

          <section className="highlights" aria-labelledby="highlights-title">
            <div className="highlights__head">
              <h2 id="highlights-title" className="highlights__title">{t.highlightsTitle}</h2>
              <button
                type="button"
                className="quick-btn"
                onClick={() => (readingHighlights ? stop() : speak(highlights.speech, 'highlights'))}
                aria-pressed={readingHighlights}
              >
                <span aria-hidden="true">{readingHighlights ? '⏹ ' : '🔊 '}</span>
                {readingHighlights ? t.stop : t.play}
              </button>
            </div>
            <p className="highlights__note">{format(t.highlightsNote, { n: n_reviews })}</p>
            {highlights.points.length === 0 ? (
              <p>{highlights.speech}</p>
            ) : (
              <ul className="highlights__list">
                {highlights.points.map(p => (
                  <li key={p.aspect} className="highlight">
                    <span className="highlight__label">{p.label}</span>
                    <span className="highlight__text">{p.detail}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="highlights" aria-labelledby="appearance-title">
            <div className="highlights__head">
              <h2 id="appearance-title" className="highlights__title">{t.appearanceTitle}</h2>
              <button
                type="button"
                className="quick-btn"
                onClick={() => (readingAppearance ? stop() : speak(appearance, 'appearance'))}
                aria-pressed={readingAppearance}
              >
                <span aria-hidden="true">{readingAppearance ? '⏹ ' : '🔊 '}</span>
                {readingAppearance ? t.stop : t.playAppearance}
              </button>
            </div>
            <p className="highlights__note">{t.appearanceNote}</p>
            <p className="appearance__text">{appearance}</p>
          </section>
        </div>

        {/* ── Right: ask the reviews ─────────────────────────────────── */}
        <section aria-labelledby="ask-title" className="detail-qa">
          <h2 id="ask-title" className="highlights__title">{t.askTitle}</h2>

          <div
            ref={chatLogRef}
            role="log"
            aria-live="polite"
            aria-relevant="additions"
            aria-labelledby="ask-title"
            className="chat-log"
          >
            {messages.map((msg, i) => (
              <div key={i} className={`chat-msg chat-msg--${msg.role}`}>
                <span className="chat-msg__label">
                  {msg.role === 'user' ? t.you : t.assistant}
                  <span className="sr-only">: </span>
                </span>
                {msg.role === 'ai' ? (
                  <div className="chat-msg__ai">
                    <div>
                      <div className="chat-msg__bubble">{msg.content}</div>
                      <Evidence items={msg.evidence} t={t} />
                    </div>
                    <button
                      type="button"
                      className="chat-msg__speak"
                      onClick={() => (speakingId === `msg-${i}` ? stop() : speak(msg.content, `msg-${i}`))}
                      aria-pressed={speakingId === `msg-${i}`}
                      aria-label={speakingId === `msg-${i}` ? t.stop : t.readAloud}
                    >
                      <span aria-hidden="true">{speakingId === `msg-${i}` ? '⏹' : '🔊'}</span>
                    </button>
                  </div>
                ) : (
                  <div className="chat-msg__bubble">{msg.content}</div>
                )}
              </div>
            ))}
            {asking && (
              <div className="chat-loading" aria-hidden="true">
                <span>⏳</span> <span>{t.thinking}</span>
              </div>
            )}
          </div>

          <div className="quick-questions" role="group" aria-label={t.askPlaceholder}>
            {t.quick.map(q => (
              <button key={q} type="button" className="quick-btn" onClick={() => ask(q, false)} disabled={asking}>
                {q}
              </button>
            ))}
          </div>

          <form className="query-form" onSubmit={e => { e.preventDefault(); ask(question, false) }}>
            <div className="query-form__field">
              <label htmlFor="q-input" className="query-form__label">{t.askLabel}</label>
              <div className="query-form__input-row">
                <input
                  ref={inputRef}
                  id="q-input"
                  type="text"
                  className="query-form__input"
                  placeholder={t.askPlaceholder}
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  disabled={asking}
                  autoComplete="off"
                  aria-describedby="voice-help-detail"
                />
                {voiceSupported && (
                  <button
                    type="button"
                    className={`voice-btn${listening ? ' voice-btn--active' : ''}`}
                    onClick={startVoice}
                    aria-label={listening ? t.stopListening : format(t.voice, { key })}
                    aria-pressed={listening}
                    disabled={asking}
                  >
                    <MicIcon listening={listening} />
                  </button>
                )}
              </div>
              <p id="voice-help-detail" className="search-box__help">{t.voiceHelpDetail}</p>
            </div>
            <button type="submit" className="query-form__submit" disabled={asking || !question.trim()}>
              {t.send}
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
