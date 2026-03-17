import { useState, useEffect, useRef } from 'react'

const API_BASE = 'http://localhost:8000'

function StarRating({ rating, count }) {
  const full = Math.round(rating)
  const stars = '★'.repeat(full) + '☆'.repeat(5 - full)
  return (
    <p className="product-card__rating">
      <span aria-hidden="true">{stars}</span>
      {' '}{rating.toFixed(1)} ({count.toLocaleString()} reviews)
    </p>
  )
}

export default function SearchPage() {
  const [products, setProducts] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/products`)
      .then(r => {
        if (!r.ok) throw new Error('无法加载商品列表')
        return r.json()
      })
      .then(data => { setProducts(data); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [])

  const filtered = products.filter(p =>
    (p.name + ' ' + p.brand).toLowerCase().includes(query.toLowerCase())
  )

  return (
    <main id="main-content" className="page">
      <div className="search-hero">
        <h1 className="search-hero__title">Find what's right for you</h1>
        <p className="search-hero__sub">AI-powered accessible shopping assistant</p>

        <div className="search-box">
          <label htmlFor="product-search" className="sr-only">
            Search by product name or brand
          </label>
          <div className="search-box__inner">
            <svg
              className="search-box__icon"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
            <input
              ref={inputRef}
              id="product-search"
              type="search"
              className="search-box__input"
              placeholder="Search by name or brand"
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoComplete="off"
              aria-controls="product-grid"
            />
            {query && (
              <button
                className="search-box__clear"
                onClick={() => { setQuery(''); inputRef.current?.focus() }}
                aria-label="Clear search"
              >
                ×
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Screen-reader live region for result count */}
      <p
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {!loading && `${filtered.length} product${filtered.length !== 1 ? 's' : ''} found`}
      </p>

      {loading && (
        <ul className="product-grid" aria-label="Loading" aria-busy="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <li key={i}>
              <div className="product-card product-card--skeleton" aria-hidden="true" />
            </li>
          ))}
        </ul>
      )}

      {error && (
        <div className="empty-state" role="alert">
          <p>Failed to load: {error}</p>
          <p style={{ marginTop: '0.5rem', fontSize: '0.9375rem' }}>
            Make sure the backend is running (uvicorn main:app --port 8000)
          </p>
        </div>
      )}

      {!loading && !error && (
        <>
          <p className="results-count" aria-hidden="true">
            {query
              ? `${filtered.length} of ${products.length} products`
              : `All ${filtered.length} products`}
          </p>

          {filtered.length === 0 ? (
            <div className="empty-state">
              <p>No products found for "{query}". Try a different keyword.</p>
            </div>
          ) : (
            <ul
              id="product-grid"
              className="product-grid"
              role="list"
              aria-label="Product list"
            >
              {filtered.map(product => (
                <li key={product.asin} role="listitem">
                  <article
                    className="product-card"
                    aria-label={`${product.name}, ${product.brand}, CHF ${product.price.toFixed(2)}, rated ${product.rating.toFixed(1)} stars`}
                  >
                    <a
                      href={`/product/${product.asin}`}
                      className="product-card__link"
                      tabIndex={0}
                    >
                      <div className="product-card__image-wrap">
                        {product.image_url && product.image_url !== 'placeholder' ? (
                          <img
                            src={product.image_url}
                            alt={product.name}
                            className="product-card__image"
                            loading="lazy"
                          />
                        ) : (
                          <div className="product-card__placeholder" aria-hidden="true">
                            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <rect x="3" y="3" width="18" height="18" rx="2" />
                              <circle cx="8.5" cy="8.5" r="1.5" />
                              <path d="m21 15-5-5L5 21" />
                            </svg>
                          </div>
                        )}
                        <span className="product-card__category">{product.category}</span>
                      </div>

                      <div className="product-card__body">
                        <p className="product-card__brand">{product.brand}</p>
                        <h2 className="product-card__name">{product.name}</h2>
                        <StarRating rating={product.rating} count={product.review_count} />
                        <p className="product-card__price">CHF {product.price.toFixed(2)}</p>
                      </div>
                    </a>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </main>
  )
}
