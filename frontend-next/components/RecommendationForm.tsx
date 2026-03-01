'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchPlaces,
  fetchRecommendations,
  CUISINE_OPTIONS,
  PLACE_TAG_COLORS,
} from '@/lib/api';
import { ResultCard } from './ResultCard';

export function RecommendationForm() {
  const [placeOptions, setPlaceOptions] = useState<string[]>([]);
  const [selectedPlaces, setSelectedPlaces] = useState<string[]>([]);
  const [selectedCuisines, setSelectedCuisines] = useState<string[]>([]);
  const [maxPrice, setMaxPrice] = useState(10000);
  const [minRating, setMinRating] = useState(4);
  const [maxResults, setMaxResults] = useState(10);
  const [placeOpen, setPlaceOpen] = useState(false);
  const [cuisineOpen, setCuisineOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<{
    recommendations: Array<{
      name: string;
      locality?: string;
      city?: string;
      average_cost_for_two?: number;
      aggregate_rating?: number;
      badges?: string[];
      cuisines?: string[];
    }>;
  } | null>(null);

  useEffect(() => {
    fetchPlaces().then(setPlaceOptions).catch(() => setPlaceOptions([]));
  }, []);

  const removePlace = useCallback((place: string) => {
    setSelectedPlaces((p) => p.filter((x) => x !== place));
  }, []);
  const removeCuisine = useCallback((c: string) => {
    setSelectedCuisines((prev) => prev.filter((x) => x !== c));
  }, []);

  const addPlace = useCallback((place: string) => {
    if (!selectedPlaces.includes(place)) setSelectedPlaces((p) => [...p, place]);
    setPlaceOpen(false);
  }, [selectedPlaces]);
  const addCuisine = useCallback((c: string) => {
    setSelectedCuisines((prev) => [...prev, c]);
    setCuisineOpen(false);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body: Parameters<typeof fetchRecommendations>[0] = {
        price_range: { min: 0, max: maxPrice, currency: 'INR' },
        min_rating: minRating,
        max_results: maxResults,
      };
      if (selectedPlaces.length) body.location = { places: selectedPlaces };
      if (selectedCuisines.length) body.cuisines = selectedCuisines.map((x) => x.toLowerCase());
      const result = await fetchRecommendations(body);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  const recs = data?.recommendations ?? [];

  return (
    <div className="space-y-6">
      <div className="card">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {/* PLACE */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                Place
              </label>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => { setPlaceOpen(!placeOpen); setCuisineOpen(false); }}
                  className="input-base flex items-center justify-between cursor-pointer text-left"
                >
                  <span className={selectedPlaces.length ? 'text-zinc-900' : 'text-zinc-400'}>
                    {selectedPlaces.length ? `${selectedPlaces.length} selected` : 'Select areas'}
                  </span>
                  <span className="text-zinc-400 text-xs">▼</span>
                </button>
                {placeOpen && (
                  <div className="absolute z-10 mt-1 w-full rounded-lg border border-zinc-200 bg-white shadow-lg max-h-48 overflow-auto">
                    {placeOptions.map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => addPlace(p)}
                        className="w-full px-3 py-2.5 text-left text-sm hover:bg-zinc-50 first:rounded-t-lg last:rounded-b-lg"
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mt-2">
                  {selectedPlaces.map((p, i) => (
                    <span
                      key={p}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-medium ${PLACE_TAG_COLORS[i % PLACE_TAG_COLORS.length]}`}
                    >
                      {p}
                      <button
                        type="button"
                        onClick={() => removePlace(p)}
                        className="opacity-80 hover:opacity-100"
                        aria-label={`Remove ${p}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* MAX PRICE */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                Max price (INR)
              </label>
              <input
                type="number"
                min={0}
                value={maxPrice}
                onChange={(e) => setMaxPrice(Number(e.target.value) || 0)}
                className="input-base"
              />
            </div>

            {/* MIN RATING */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                Min rating
              </label>
              <div className="inline-flex items-center border border-zinc-200 rounded-lg overflow-hidden bg-white">
                <button
                  type="button"
                  onClick={() => setMinRating((r) => Math.max(0, r - 0.5))}
                  className="w-11 h-11 flex items-center justify-center bg-zinc-50 hover:bg-zinc-100 text-zinc-700 font-medium"
                >
                  −
                </button>
                <input
                  type="number"
                  min={0}
                  max={5}
                  step={0.5}
                  value={minRating}
                  onChange={(e) => setMinRating(Number(e.target.value) || 0)}
                  className="w-14 text-center border-x border-zinc-200 py-2 text-sm focus:outline-none focus:ring-0"
                />
                <button
                  type="button"
                  onClick={() => setMinRating((r) => Math.min(5, r + 0.5))}
                  className="w-11 h-11 flex items-center justify-center bg-zinc-50 hover:bg-zinc-100 text-zinc-700 font-medium"
                >
                  +
                </button>
              </div>
            </div>

            {/* CUISINES */}
            <div className="sm:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                Cuisines
              </label>
              <div className="relative">
                <button
                  type="button"
                  onClick={() => { setCuisineOpen(!cuisineOpen); setPlaceOpen(false); }}
                  className="input-base flex items-center justify-between cursor-pointer text-left"
                >
                  <span className={selectedCuisines.length ? 'text-zinc-900' : 'text-zinc-400'}>
                    {selectedCuisines.length ? `${selectedCuisines.length} selected` : 'Select cuisines'}
                  </span>
                  <span className="text-zinc-400 text-xs">▼</span>
                </button>
                {cuisineOpen && (
                  <div className="absolute z-10 mt-1 w-full rounded-lg border border-zinc-200 bg-white shadow-lg max-h-48 overflow-auto">
                    {CUISINE_OPTIONS.filter((c) => !selectedCuisines.includes(c)).map((c) => (
                      <button
                        key={c}
                        type="button"
                        onClick={() => addCuisine(c)}
                        className="w-full px-3 py-2.5 text-left text-sm hover:bg-zinc-50 first:rounded-t-lg last:rounded-b-lg"
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                )}
                <div className="flex flex-wrap gap-2 mt-2">
                  {selectedCuisines.map((c) => (
                    <span
                      key={c}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-sm font-medium bg-[#e23744] text-white"
                    >
                      {c}
                      <button
                        type="button"
                        onClick={() => removeCuisine(c)}
                        className="opacity-90 hover:opacity-100"
                        aria-label={`Remove ${c}`}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* MAX RESULTS */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                Max results
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value) || 10)}
                className="input-base"
              />
            </div>
          </div>

          <div className="flex justify-center pt-2">
            <button type="submit" disabled={loading} className="btn-primary min-w-[240px]">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                <path d="M12 2l1.5 4.5L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1.5L12 2z" />
              </svg>
              {loading ? 'Getting recommendations…' : 'Get AI Recommendations'}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-100 text-red-700 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {recs.length === 0 && !error && data !== null && (
        <div className="card text-center text-zinc-500 py-10">
          No recommendations found. Try more areas or relax filters.
        </div>
      )}

      {recs.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-zinc-800">Recommendations</h2>
          <div className="space-y-3">
            {recs.map((r, i) => (
              <ResultCard key={i} recommendation={r} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
