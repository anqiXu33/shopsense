import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'

const API_BASE = 'http://localhost:8000'

const QUICK_QUESTIONS = [
  '适合零下10度吗？',
  '对皮肤敏感友好吗？',
  '评价里有提到缩水吗？',
  '颜色和图片一致吗？',
  '适合175cm 65kg吗？',
]

// ── Agent Sub-panels ─────────────────────────────────────────────────────

function ToolSelectionPanel({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>暂无数据</p>
  return (
    <>
      <p className="tool-reasoning">{data.reasoning}</p>
      <div className="tool-badges" aria-label="已选择的工具">
        {data.tools.map(t => (
          <span key={t} className="tool-badge">{t}</span>
        ))}
      </div>
    </>
  )
}

function ToolExecutionPanel({ data }) {
  if (!data || data.length === 0) return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>暂无数据</p>
  return (
    <div role="list" aria-label="工具执行结果">
      {data.map(r => (
        <div key={r.tool_name} className="tool-result-row" role="listitem">
          <span className="tool-result-row__name">{r.tool_name}</span>
          <span className="tool-result-row__dur" aria-label={`耗时 ${r.duration_ms} 毫秒`}>
            {r.duration_ms}ms
          </span>
          <div className="tool-result-row__progress-wrap">
            <progress
              className="tool-result-row__progress"
              value={r.relevance_score}
              max={1}
              aria-label={`相关性 ${Math.round(r.relevance_score * 100)}%`}
            />
            <span className="tool-result-row__score" aria-hidden="true">
              {Math.round(r.relevance_score * 100)}%
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function ContextPanel({ text }) {
  if (!text) return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>暂无数据</p>
  return (
    <pre className="context-pre" tabIndex={0} aria-label="上下文组装内容">
      {text}
    </pre>
  )
}

function ConflictPanel({ data }) {
  if (!data) return <p style={{ color: 'var(--text-muted)', fontSize: '0.9375rem' }}>暂无数据</p>
  return (
    <>
      {data.has_conflict ? (
        <p className="conflict-warn">⚠ 检测到矛盾</p>
      ) : (
        <p className="conflict-ok">✓ 无矛盾</p>
      )}
      <p className="conflict-detail">{data.details}</p>
    </>
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

  const [statusAssertive, setStatusAssertive] = useState('')
  const [statusPolite, setStatusPolite] = useState('')

  const [speaking, setSpeaking] = useState(false)
  const [speakingMsgIdx, setSpeakingMsgIdx] = useState(null)

  const inputRef = useRef(null)
  const chatLogRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/products/${asin}`)
      .then(r => {
        if (!r.ok) throw new Error('商品不存在')
        return r.json()
      })
      .then(data => { setProduct(data); setLoadingProduct(false) })
      .catch(err => { setProductError(err.message); setLoadingProduct(false) })
  }, [asin])

  // Scroll chat to bottom on new messages
  useEffect(() => {
    if (chatLogRef.current) {
      chatLogRef.current.scrollTop = chatLogRef.current.scrollHeight
    }
  }, [messages, querying])

  function speakText(text, idx) {
    if (speaking) {
      speechSynthesis.cancel()
      setSpeaking(false)
      setSpeakingMsgIdx(null)
      return
    }
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = 'zh-CN'
    utt.onend = () => { setSpeaking(false); setSpeakingMsgIdx(null) }
    setSpeaking(true)
    setSpeakingMsgIdx(idx)
    speechSynthesis.speak(utt)
  }

  async function submitQuery(q) {
    const text = (q ?? question).trim()
    if (!text || querying) return

    setQuestion('')
    setQuerying(true)
    setStatusAssertive('正在查询，请稍候')
    setMessages(prev => [...prev, { role: 'user', content: text }])

    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asin, question: text }),
      })
      if (!res.ok) throw new Error('查询失败')
      const data = await res.json()

      setMessages(prev => [...prev, { role: 'ai', content: data.answer, agentData: data }])
      setLatestAgent(data)
      setStatusAssertive('')
      setStatusPolite(`回复已生成，共 ${data.answer.length} 字`)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', content: `错误：${err.message}` }])
      setStatusAssertive('')
      setStatusPolite('查询出错')
    } finally {
      setQuerying(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  async function handleImageTts() {
    if (speaking) {
      speechSynthesis.cancel()
      setSpeaking(false)
      setSpeakingMsgIdx(null)
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asin, question: 'describe image' }),
      })
      const data = await res.json()
      speakText(data.answer, 'image')
    } catch {
      // silently fail TTS
    }
  }

  if (loadingProduct) {
    return <main id="main-content" className="page-loading" aria-busy="true">加载中…</main>
  }
  if (productError) {
    return (
      <main id="main-content" className="page-error" role="alert">
        加载失败：{productError}
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

      <a href="/" className="back-link" aria-label="返回商品列表">
        ← 返回
      </a>

      <div className="detail-layout">
        {/* ── Left: Product Info ─────────────────────────────────── */}
        <section aria-label="商品信息">
          <div className="detail-product">
            <div className="detail-product__image-wrap">
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
            </div>

            <button
              className="detail-product__tts-btn"
              onClick={handleImageTts}
              aria-label={speaking && speakingMsgIdx === 'image' ? '停止朗读商品图片描述' : '朗读商品图片描述'}
            >
              {speaking && speakingMsgIdx === 'image' ? '⏹ 停止朗读' : '🔊 朗读图片描述'}
            </button>

            <div className="detail-product__info">
              <h1 className="detail-product__name">{name}</h1>

              <p className="detail-product__field">
                <span className="sr-only">品牌：</span>
                {brand}
              </p>

              <p className="detail-product__price">
                <span className="sr-only">价格：</span>
                ¥{price.toFixed(2)}
              </p>

              <p className="detail-product__field">
                <span className="sr-only">评分：</span>
                {'★'.repeat(Math.round(rating))}{'☆'.repeat(5 - Math.round(rating))}
                {' '}{rating.toFixed(1)} 分，共 {review_count.toLocaleString()} 条评价
              </p>

              {attributes?.material && (
                <p className="detail-product__field">
                  <span className="sr-only">材质：</span>
                  {attributes.material}
                </p>
              )}

              {attributes?.color && (
                <p className="detail-product__field">
                  <span className="sr-only">颜色：</span>
                  {attributes.color}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── Right: Q&A ─────────────────────────────────────────── */}
        <section aria-label="AI 购物助手问答" className="detail-qa">
          {/* Chat log */}
          <div
            ref={chatLogRef}
            role="log"
            aria-live="polite"
            aria-label="对话记录"
            aria-relevant="additions"
            className="chat-log"
          >
            {messages.length === 0 && !querying && (
              <p className="chat-empty">向助手提问，获取关于此商品的专业建议。</p>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`chat-msg chat-msg--${msg.role}`}
              >
                <span className="chat-msg__label" aria-hidden="true">
                  {msg.role === 'user' ? '你' : 'ShopSense'}
                </span>
                <div className="chat-msg__bubble">{msg.content}</div>
                {msg.role === 'ai' && (
                  <div className="chat-msg__actions">
                    <button
                      className="chat-msg__tts"
                      onClick={() => speakText(msg.content, i)}
                      aria-label={speaking && speakingMsgIdx === i ? '停止朗读此回复' : '朗读此回复'}
                    >
                      {speaking && speakingMsgIdx === i ? '⏹' : '🔊'}
                    </button>
                  </div>
                )}
              </div>
            ))}

            {querying && (
              <div className="chat-loading" aria-busy="true" role="status">
                <span aria-hidden="true">⏳</span>
                <span>正在分析…</span>
              </div>
            )}
          </div>

          {/* Quick questions */}
          <div
            className="quick-questions"
            role="group"
            aria-label="快捷问题"
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
            aria-label="向助手提问"
            onSubmit={e => { e.preventDefault(); submitQuery() }}
          >
            <div className="query-form__field">
              <label htmlFor="q-input" className="query-form__label">
                输入您的问题
              </label>
              <input
                ref={inputRef}
                id="q-input"
                type="text"
                className="query-form__input"
                placeholder="例如：适合冬天户外穿吗？"
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
              aria-label="发送问题"
            >
              发送
            </button>
          </form>
        </section>
      </div>

      {/* ── Agent Transparency Panel ──────────────────────────────── */}
      <section className="agent-section" aria-label="Agent 推理过程">
        <button
          className="agent-toggle"
          aria-expanded={agentOpen}
          aria-controls="agent-panel-content"
          onClick={() => setAgentOpen(v => !v)}
        >
          Agent 推理过程
          <span className="agent-toggle__chevron" aria-hidden="true">
            {agentOpen ? '▾' : '▸'}
          </span>
        </button>

        {agentOpen && (
          <div id="agent-panel-content" className="agent-body">
            <div className="agent-grid">
              <div className="agent-subpanel">
                <h2 className="agent-subpanel__title">Tool Selection</h2>
                <ToolSelectionPanel data={latestAgent?.tool_selection} />
              </div>

              <div className="agent-subpanel">
                <h2 className="agent-subpanel__title">Tool Execution</h2>
                <ToolExecutionPanel data={latestAgent?.tool_results} />
              </div>

              <div className="agent-subpanel">
                <h2 className="agent-subpanel__title">Context Assembly</h2>
                <ContextPanel text={latestAgent?.context_assembly} />
              </div>

              <div className="agent-subpanel">
                <h2 className="agent-subpanel__title">Conflict Detection</h2>
                <ConflictPanel data={latestAgent?.conflict_detection} />
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
