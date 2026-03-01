const getBaseUrl = () => {
  if (typeof window === 'undefined') return '';
  return process.env.NEXT_PUBLIC_API_URL || '';
};

export async function fetchPlaces(): Promise<string[]> {
  const res = await fetch(`${getBaseUrl()}/recommendations/places`);
  const data = await res.json();
  return data.places ?? [];
}

export async function fetchRecommendations(body: {
  location?: { places?: string[] };
  price_range?: { min: number; max: number; currency: string };
  min_rating?: number;
  cuisines?: string[];
  max_results?: number;
}) {
  const res = await fetch(`${getBaseUrl()}/recommendations/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

export const CUISINE_OPTIONS = [
  'North Indian', 'Chinese', 'South Indian', 'Italian', 'Cafe', 'Bakery',
  'Fast Food', 'Biryani', 'Desserts', 'Continental', 'Mughlai', 'Thai',
  'Japanese', 'Mexican', 'Street Food', 'Seafood', 'Healthy Food', 'Beverages',
];

export const PLACE_TAG_COLORS = [
  'tag-place-0', 'tag-place-1', 'tag-place-2', 'tag-place-3', 'tag-place-4', 'tag-place-5',
];
