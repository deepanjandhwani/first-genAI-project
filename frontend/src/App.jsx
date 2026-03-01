import { useState, useEffect } from 'react'
import './App.css'

const API = '' // same origin when served from FastAPI; dev proxy uses /recommendations

function App() {
  const [places, setPlaces] = useState([])
  const [place, setPlace] = useState('')
  const [minPrice, setMinPrice] = useState(0)
  const [maxPrice, setMaxPrice] = useState(10000)
  const [minRating, setMinRating] = useState(0)
  const [cuisines, setCuisines] = useState('')
  const [maxResults, setMaxResults] = useState(10)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API}/recommendations/places`)
      .then((r) => r.json())
      .then((data) => setPlaces(data.places || []))
      .catch(() => setPlaces([]))
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    const body = {
      location: place ? { city: place, locality: place } : undefined,
      price_range: { min: minPrice, max: maxPrice, currency: 'INR' },
      min_rating: minRating,
      cuisines: cuisines.trim() ? cuisines.split(',').map((s) => s.trim()).filter(Boolean) : undefined,
      max_results: maxResults,
    }
    fetch(`${API}/recommendations/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then((r) => r.json())
      .then((data) => {
        setResults(data)
        if (data.detail) setError(data.detail)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  const recs = results?.recommendations ?? []

  return (
    <div className="app">
      <header className="header">
        <h1>Restaurant Recommendations</h1>
      </header>

      <main className="container">
        <section className="card form-card">
          <form onSubmit={handleSubmit} className="form">
            <div className="form-row">
              <label>
                <span>Place</span>
                <select
                  value={place}
                  onChange={(e) => setPlace(e.target.value)}
                  className="input select"
                >
                  <option value="">All areas</option>
                  {places.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Max results</span>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="input"
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                <span>Min price (₹)</span>
                <input
                  type="number"
                  min={0}
                  value={minPrice}
                  onChange={(e) => setMinPrice(Number(e.target.value))}
                  className="input"
                />
              </label>
              <label>
                <span>Max price (₹)</span>
                <input
                  type="number"
                  min={0}
                  value={maxPrice}
                  onChange={(e) => setMaxPrice(Number(e.target.value))}
                  className="input"
                />
              </label>
              <label>
                <span>Min rating</span>
                <input
                  type="number"
                  min={0}
                  max={5}
                  step={0.1}
                  value={minRating}
                  onChange={(e) => setMinRating(Number(e.target.value))}
                  className="input"
                />
              </label>
            </div>
            <div className="form-row">
              <label className="full">
                <span>Cuisines (comma-separated)</span>
                <input
                  type="text"
                  placeholder="e.g. north indian, chinese"
                  value={cuisines}
                  onChange={(e) => setCuisines(e.target.value)}
                  className="input"
                />
              </label>
            </div>
            <button type="submit" className="btn" disabled={loading}>
              {loading ? 'Finding…' : 'Get recommendations'}
            </button>
          </form>
        </section>

        {error && (
          <div className="card error-card">{error}</div>
        )}

        {results && !error && (
          <section className="results">
            {recs.length === 0 ? (
              <div className="card empty-card">
                No recommendations found. Try &quot;All areas&quot; or relax filters.
              </div>
            ) : (
              <>
                <h2 className="results-title">{recs.length} recommendation{recs.length !== 1 ? 's' : ''}</h2>
                <div className="cards">
                  {recs.map((r) => (
                    <article key={r.candidate_id} className="card rec-card">
                      <div className="rec-header">
                        <h3 className="rec-name">{r.name}</h3>
                        <span className="rec-rating">{r.aggregate_rating}★</span>
                      </div>
                      <div className="rec-meta">
                        {[r.locality, r.city].filter(Boolean).join(' · ')}
                        {r.average_cost_for_two > 0 && ` · ₹${r.average_cost_for_two} for two`}
                      </div>
                      {r.badges?.length > 0 && (
                        <div className="badges">
                          {r.badges.map((b) => (
                            <span key={b} className="badge">{b}</span>
                          ))}
                        </div>
                      )}
                      {r.cuisines?.length > 0 && (
                        <div className="rec-cuisines">{r.cuisines.join(', ')}</div>
                      )}
                      {r.why_recommended && (
                        <p className="rec-why">{r.why_recommended}</p>
                      )}
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </div>
  )
}

export default App
