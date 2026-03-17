import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

const QUICK_QUESTIONS = [
  'Is it suitable for -10°C weather?',
  'Is it skin-sensitive friendly?',
  'Do reviews mention shrinking?',
  'Does the color match the photos?',
  'Fits someone 175cm / 65kg?',
]

// ── Agent Sub-panels ─────────────────────────────────────────────────────

const TOOL_ICON = { review_search: '💬', knowledge_search: '📚', visual_search: '🖼️' }

function ReActTracePanel({ trace }) {
  if (!trace || trace.length === 0)
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>No data yet</p>

  return (
    <div role="list" aria-label="ReAct reasoning trace">
      {trace.map((step, i) => (
        <div key={i} className="react-step" role="listitem">
          <span className="react-step__iter">Iter {step.iteration}</span>

          {step.action === 'final_answer' && (
            <span className="react-step__final react-step__final--ok">→ answered</span>
          )}
          {step.action === 'forced_final_answer' && (
            <span className="react-step__final react-step__final--warn">→ forced answer</span>
          )}

          {step.actions && (
            <div className="react-step__body">
              <div className="react-step__actions">
                {step.actions.map((a, j) => (
                  <span key={j} className="tool-badge">
                    {TOOL_ICON[a.tool] ?? '🔍'} {a.tool.replace('_search', '')}({a.limit})
                  </span>
                ))}
              </div>
              <div className="react-step__obs">
                {step.observations?.map((o, j) => (
                  <span key={j} className="react-obs">
                    {o.results} res · {Math.round(o.score * 100)}% · {o.duration_ms}ms
                  </span>
                ))}
              </div>
              {step.reflection?.next_action === 'search_more' && (
                <div className="react-step__reflection">
                  <span className="react-step__next-action">→ search more</span>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function ContextSignalsPanel({ trace }) {
  const steps = (trace || []).filter(s => s.context_injection || s.reflection)
  if (steps.length === 0)
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>No data yet</p>

  return (
    <div>
      {steps.map((step, i) => (
        <div key={i} style={{ marginBottom: i < steps.length - 1 ? '0.75rem' : 0 }}>
          <span style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
            After iter {step.iteration}
          </span>
          {step.reflection?.gaps && step.reflection.gaps !== 'none' && step.reflection.gaps !== 'null' && (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic', margin: '0.2rem 0 0.3rem' }}>
              Gap: {step.reflection.gaps}
            </div>
          )}
          {step.context_injection && (
            <div className="react-step__injection" style={{ marginTop: '0.2rem' }}>
              <span className="react-step__injection-label">↩</span>
              {step.context_injection}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function SessionContextPanel({ userCtx, messages }) {
  // Last 2 full turns sent to the LLM (matches backend history[-4:])
  const turns = []
  const allMsgs = messages.slice(-4)
  for (let i = 0; i < allMsgs.length - 1; i++) {
    const m = allMsgs[i]
    const next = allMsgs[i + 1]
    if (m.role === 'user' && next.role === 'ai') {
      turns.push({ q: m.content, summary: next.retrieval_summary })
      i++ // skip the paired ai message
    }
  }

  const slots = [
    userCtx.height       && `Height: ${userCtx.height}cm`,
    userCtx.weight       && `Weight: ${userCtx.weight}kg`,
    userCtx.temp_target  && `Temp: ${userCtx.temp_target}`,
    userCtx.skin_sensitive != null && `Skin sensitive: ${userCtx.skin_sensitive ? 'yes' : 'no'}`,
  ].filter(Boolean)

  return (
    <div className="rq-panel">
      <div className="rq-row">
        <span className="rq-label">History in context</span>
        <span className="rq-badge">{turns.length} turn{turns.length !== 1 ? 's' : ''}</span>
      </div>

      {turns.length > 0 ? (
        <ul className="rq-hints" style={{ marginTop: '0.5rem' }}>
          {turns.map((t, i) => (
            <li key={i} style={{ marginBottom: '0.4rem' }}>
              <span style={{ opacity: 0.7 }}>Q: </span>
              <span>{t.q.length > 48 ? t.q.slice(0, 48) + '…' : t.q}</span>
              {t.summary && (
                <span className="react-obs" style={{ display: 'block', marginTop: '0.15rem' }}>
                  {t.summary}
                </span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', margin: '0.5rem 0 0 0' }}>
          No prior turns in context
        </p>
      )}

      {slots.length > 0 && (
        <>
          <div className="rq-row" style={{ marginTop: '0.75rem' }}>
            <span className="rq-label">User profile</span>
          </div>
          <ul className="rq-hints">
            {slots.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        </>
      )}
    </div>
  )
}

const CONFIDENCE_LABEL = { high: '● High', medium: '◐ Medium', low: '○ Low' }

function RetrievalQualityPanel({ trace, conflict }) {
  const reflections = (trace || []).filter(s => s.reflection).map(s => ({
    iteration: s.iteration,
    ...s.reflection,
  }))
  if (reflections.length === 0 && !conflict)
    return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>No data yet</p>
  return (
    <div className="rq-panel">
      {reflections.length > 0 && (
        <div className="rq-row rq-row--conf">
          <span className="rq-label">Confidence</span>
          <span className="rq-conf-track">
            {reflections.map((r, i) => (
              <span key={i} className="rq-conf-step">
                <span className="rq-conf-iter">iter {r.iteration}</span>
                <span className={`rq-badge rq-badge--${r.confidence}`}>
                  {CONFIDENCE_LABEL[r.confidence] ?? r.confidence}
                </span>
                {i < reflections.length - 1 && (
                  <span className="rq-conf-arrow">→</span>
                )}
              </span>
            ))}
          </span>
        </div>
      )}
      {conflict && (
        <div className="rq-row">
          <span className="rq-label">Consistency</span>
          {conflict.has_conflict
            ? <span className="rq-badge rq-badge--conflict">⚠ {conflict.details}</span>
            : <span className="rq-badge rq-badge--ok">✓ No conflicts</span>}
        </div>
      )}
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────

export default function DetailPage() {
  const { asin } = useParams()
  const [product, setProduct] = useState(null)
  const [loadingProduct, setLoadingProduct] = useState(true)
  const [productError, setProductError] = useState(null)

  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [querying, setQuerying] = useState(false)
  const [latestAgent, setLatestAgent] = useState(null)
  const [agentOpen, setAgentOpen] = useState(false)
  const [userContext, setUserContext] = useState({})

  const [statusAssertive, setStatusAssertive] = useState('')
  const [statusPolite, setStatusPolite] = useState('')

  const [speaking, setSpeaking] = useState(false)
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState(null)
  const [ttsLoading, setTtsLoading] = useState(false)

  const inputRef = useRef(null)
  const chatLogRef = useRef(null)
  const voicesRef = useRef([])
  const audioRef = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    fetch(`${API_BASE}/api/products/${asin}`)
      .then(r => {
        if (!r.ok) throw new Error('商品不存在')
        return r.json()
      })
      .then(data => { setProduct(data); setLoadingProduct(false) })
      .catch(err => { setProductError(err.message); setLoadingProduct(false) })
  }, [asin])

  // Load best available browser voices
  useEffect(() => {
    function load() { voicesRef.current = speechSynthesis.getVoices() }
    load()
    speechSynthesis.addEventListener('voiceschanged', load)
    return () => speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  // Stop all TTS when leaving the page
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      speechSynthesis.cancel()
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
    }
  }, [])

  // Scroll chat to bottom on new messages
  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight
    }
  }, [messages, querying])

  function pickVoice(text) {
    const isChinese = /[\u4e00-\u9fff]/.test(text)
    const prefix = isChinese ? 'zh' : 'en'
    const candidates = voicesRef.current.filter(v => v.lang.startsWith(prefix))
    // Prefer neural / natural / enhanced voices (Edge, macOS, Windows all expose these)
    const PREF = ['Natural', 'Neural', 'Online', 'Enhanced', 'Premium', 'Meijia', 'Xiaoxiao', 'Xiaoyi', 'Yunxi']
    for (const p of PREF) {
      const v = candidates.find(c => c.name.includes(p))
      if (v) return v
    }
    return candidates[0] || null
  }

  function stopSpeaking() {
    speechSynthesis.cancel()
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }
    setSpeaking(false)
    setSpeakingMsgIdx(null)
    setTtsLoading(false)
  }

  async function speakText(text, idx) {
    if (!mountedRef.current) return
    if (speaking || ttsLoading) { stopSpeaking(); return }

    setTtsLoading(true)
    setSpeakingMsgIdx(idx)

    // Try backend TTS (OpenAI tts-1-hd / DashScope CosyVoice)
    try {
      const res = await fetch(`${API_BASE}/api/tts/speech?text=${encodeURIComponent(text)}`)
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const audio = new Audio(url)
        audioRef.current = audio
        setTtsLoading(false)
        setSpeaking(true)
        audio.onended = () => { URL.revokeObjectURL(url); audioRef.current = null; setSpeaking(false); setSpeakingMsgIdx(null) }
        audio.onerror = () => { setSpeaking(false); setSpeakingMsgIdx(null); setTtsLoading(false) }
        audio.play()
        return
      }
    } catch { /* fall through */ }

    setTtsLoading(false)

    // Browser TTS fallback — pick best available neural voice
    const isChinese = /[\u4e00-\u9fff]/.test(text)
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = isChinese ? 'zh-CN' : 'en-US'
    const voice = pickVoice(text)
    if (voice) utt.voice = voice
    utt.rate = 0.9
    utt.pitch = 1.0
    utt.onend = () => { setSpeaking(false); setSpeakingMsgIdx(null) }
    setSpeaking(true)
    speechSynthesis.speak(utt)
  }

  function extractSlots(text, prev) {
    const updated = { ...prev }
    const t = text.toLowerCase()
    const heightMatch = text.match(/(\d{3})\s*cm/i) || text.match(/身高\s*(\d{3})/)
    if (heightMatch) updated.height = parseInt(heightMatch[1])
    const weightMatch = text.match(/(\d{2,3})\s*kg/i) || text.match(/体重\s*(\d{2,3})/)
    if (weightMatch) updated.weight = parseInt(weightMatch[1])
    const tempMatch = text.match(/-\s*(\d+)\s*[°℃c度]/) || text.match(/零下\s*(\d+)/)
    if (tempMatch) updated.temp_target = `-${tempMatch[1]}°C`
    if (/敏感肌|过敏|eczema|sensitive skin|skin sensitive/i.test(t)) updated.skin_sensitive = true
    return updated
  }

  async function submitQuery(q) {
    const text = (q ?? question).trim()
    if (!text || querying) return

    setQuestion('')
    setQuerying(true)
    setStatusAssertive('Querying, please wait…')

    // Extract slots before updating messages (messages hasn't been updated yet)
    const newContext = extractSlots(text, userContext)
    if (JSON.stringify(newContext) !== JSON.stringify(userContext)) {
      setUserContext(newContext)
    }

    // Snapshot current messages for history (before this turn is appended).
    // For AI messages, prepend a retrieval summary so the LLM knows what was
    // already searched in prior turns and avoids redundant searches.
    const historySnapshot = messages.slice(-4).map(m => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.role === 'ai' && m.retrieval_summary
        ? `[Retrieved: ${m.retrieval_summary}]\n${m.content}`
        : m.content,
    }))

    setMessages(prev => [...prev, { role: 'user', content: text }])

    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asin, question: text, history: historySnapshot, user_context: newContext }),
      })
      if (!res.ok) throw new Error('Query failed')
      const data = await res.json()

      setMessages(prev => [...prev, { role: 'ai', content: data.answer, retrieval_summary: data.retrieval_summary, agentData: data }])
      setLatestAgent(data)
      setStatusAssertive('')
      setStatusPolite(`Reply generated (${data.answer.length} characters)`)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: `Error: ${err.message}` }])
      setStatusAssertive('')
      setStatusPolite('Query failed')
    } finally {
      setQuerying(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  async function handleImageTts() {
    if (speaking) { stopSpeaking(); return }
    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asin, question: 'describe image' }),
      })
      const data = await res.json()
      if (mountedRef.current) speakText(data.answer, 'image')
    } catch {
      // silently fail TTS
    }
  }

  if (loadingProduct) {
    return <main id="main-content" className="page-loading" aria-busy="true">Loading…</main>
  }
  if (productError) {
    return (
      <main id="main-content" className="page-error" role="alert">
        Failed to load: {productError}
      </main>
    )
  }
  if (!product) return null

  const { name, brand, price, image_url, rating, review_count, description, attributes } = product

  return (
    <main id="main-content" className="page">
      {/* Hidden live regions */}
      <div aria-live="assertive" aria-atomic="true" className="sr-only">
        {statusAssertive}
      </div>
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {statusPolite}
      </div>

      <Link to="/" className="back-link" aria-label="Back to product list">
        ← Back
      </Link>

      <div className="detail-layout">
        {/* ── Left: Product Info ─────────────────────────────────── */}
        <section aria-label="Product information">
          <div className="detail-product">
            <button
              className="detail-product__image-wrap"
              onClick={handleImageTts}
              aria-label={speaking && speakingMsgIdx === 'image' ? 'Stop reading image description' : 'Click image to hear description aloud'}
            >
              {image_url && image_url !== 'placeholder' ? (
                <img
                  src={image_url}
                  alt={name}
                  className="detail-product__image"
                />
              ) : (
                <div className="detail-product__placeholder" aria-hidden="true">
                  <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="m21 15-5-5L5 21" />
                  </svg>
                </div>
              )}
              <span className="detail-product__tts-hint" aria-hidden="true">
                {ttsLoading && speakingMsgIdx === 'image' ? '⏳ Loading…' : speaking && speakingMsgIdx === 'image' ? '⏹ Stop' : '🔊 Read image'}
              </span>
            </button>

            <div className="detail-product__info">
              <h1 className="detail-product__name">{name}</h1>

              <p className="detail-product__field">
                <span className="sr-only">Brand: </span>
                {brand}
              </p>

              <p className="detail-product__price">
                <span className="sr-only">Price: </span>
                CHF {price.toFixed(2)}
              </p>

              <p className="detail-product__field">
                <span className="sr-only">Rating: </span>
                {'★'.repeat(Math.round(rating))}{'☆'.repeat(5 - Math.round(rating))}
                {' '}{rating.toFixed(1)} — {review_count.toLocaleString()} reviews
              </p>

              {attributes?.material && (
                <p className="detail-product__field">
                  <span className="sr-only">Material: </span>
                  {attributes.material}
                </p>
              )}

              {attributes?.color && (
                <p className="detail-product__field">
                  <span className="sr-only">Color: </span>
                  {attributes.color}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── Right: Q&A ─────────────────────────────────────────── */}
        <section aria-label="AI shopping assistant Q&A" className="detail-qa">
          {/* Chat log */}
          <div
            ref={chatLogRef}
            role="log"
            aria-live="polite"
            aria-label="Conversation history"
            aria-relevant="additions"
            className="chat-log"
          >
            {messages.length === 0 && !querying && (
              <p className="chat-empty">Ask the assistant for advice about this product.</p>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`chat-msg chat-msg--${msg.role}`}
              >
                <span className="chat-msg__label" aria-hidden="true">
                  {msg.role === 'user' ? 'You' : 'ShopSense'}
                </span>
                {msg.role === 'ai' ? (
                  <button
                    className="chat-msg__bubble chat-msg__bubble--tts"
                    onClick={() => speakText(msg.content, i)}
                    aria-label={speaking && speakingMsgIdx === i ? 'Stop reading this reply' : 'Click to read this reply aloud'}
                  >
                    {msg.content}
                    <span className="chat-msg__tts-hint" aria-hidden="true">
                      {ttsLoading && speakingMsgIdx === i ? ' ⏳' : speaking && speakingMsgIdx === i ? ' ⏹' : ' 🔊'}
                    </span>
                  </button>
                ) : (
                  <div className="chat-msg__bubble">{msg.content}</div>
                )}
              </div>
            ))}

            {querying && (
              <div className="chat-loading" aria-busy="true" role="status">
                <span aria-hidden="true">⏳</span>
                <span>Analyzing…</span>
              </div>
            )}
          </div>

          {/* Quick questions */}
          <div
            className="quick-questions"
            role="group"
            aria-label="Quick questions"
          >
            {QUICK_QUESTIONS.map(q => (
              <button
                key={q}
                className="quick-btn"
                onClick={() => submitQuery(q)}
                disabled={querying}
                aria-disabled={querying}
              >
                {q}
              </button>
            ))}
          </div>

          {/* Input form */}
          <form
            className="query-form"
            aria-label="Ask the assistant"
            onSubmit={e => { e.preventDefault(); submitQuery() }}
          >
            <div className="query-form__field">
              <label htmlFor="q-input" className="query-form__label">
                Your question
              </label>
              <input
                ref={inputRef}
                id="q-input"
                type="text"
                className="query-form__input"
                placeholder="e.g. Is it warm enough for winter outdoor use?"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                disabled={querying}
                aria-disabled={querying}
                autoComplete="off"
              />
            </div>
            <button
              type="submit"
              className="query-form__submit"
              disabled={querying || !question.trim()}
              aria-label="Send question"
            >
              Send
            </button>
          </form>
        </section>
      </div>

      {/* ── Agent Transparency Panel ──────────────────────────────── */}
      <section className="agent-section" aria-label="Agent reasoning process">
        <button
          className="agent-toggle"
          aria-expanded={agentOpen}
          aria-controls="agent-panel-content"
          onClick={() => setAgentOpen(v => !v)}
        >
          Agent Reasoning
          <span className="agent-toggle__chevron" aria-hidden="true">
            {agentOpen ? '▾' : '▸'}
          </span>
        </button>

        {agentOpen && (
          <div id="agent-panel-content" className="agent-body">
            <div className="agent-grid">
              <div className="agent-left-stack">
                <div className="agent-subpanel">
                  <h2 className="agent-subpanel__title">Retrieval Iterations</h2>
                  <ReActTracePanel trace={latestAgent?.reasoning_trace} />
                </div>

                <div className="agent-subpanel">
                  <h2 className="agent-subpanel__title">Session Context</h2>
                  <SessionContextPanel userCtx={userContext} messages={messages} />
                </div>
              </div>

              <div className="agent-right-stack">
                <div className="agent-subpanel">
                  <h2 className="agent-subpanel__title">Retrieval Signals</h2>
                  <RetrievalQualityPanel trace={latestAgent?.reasoning_trace} conflict={latestAgent?.conflict_detection} />
                </div>

                <div className="agent-subpanel">
                  <h2 className="agent-subpanel__title">Context Injected</h2>
                  <ContextSignalsPanel trace={latestAgent?.reasoning_trace} />
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
