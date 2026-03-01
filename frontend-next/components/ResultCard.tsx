'use client';

function badgeClass(b: string): string {
  const lower = b.toLowerCase();
  if (lower.includes('highly rated')) return 'bg-emerald-500/90 text-white';
  if (lower.includes('budget')) return 'bg-amber-500/90 text-white';
  if (lower.includes('top match')) return 'bg-[#e23744] text-white';
  return 'bg-zinc-200 text-zinc-700';
}

type Rec = {
  name: string;
  locality?: string;
  city?: string;
  average_cost_for_two?: number;
  aggregate_rating?: number;
  badges?: string[];
  cuisines?: string[];
};

export function ResultCard({ recommendation: r }: { recommendation: Rec }) {
  const locParts = [r.locality, r.city].filter(Boolean);
  const seen = new Set<string>();
  const uniqueLoc = locParts.filter((p) => {
    const key = (p || '').trim().toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const loc = uniqueLoc.join(' · ');
  const badges = (r.badges ?? []).map((b) => (
    <span key={b} className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium ${badgeClass(b)}`}>
      {b}
    </span>
  ));
  const cuisines = (r.cuisines ?? []).slice(0, 5).map((c) => (
    <span key={c} className="inline-block px-2 py-0.5 rounded-md text-xs bg-zinc-100 text-zinc-600">
      {c}
    </span>
  ));

  return (
    <div className="card hover:shadow-card-hover transition-shadow">
      <div className="font-semibold text-zinc-900 text-lg mb-1">{r.name}</div>
      <div className="flex flex-wrap items-center gap-x-1 gap-y-0.5 text-sm text-zinc-500 mb-2">
        <span className="inline-block">📍</span>
        <span>{loc}</span>
        <span className="text-zinc-300">·</span>
        <span>₹ {(r.average_cost_for_two ?? 0)} for two</span>
        <span className="text-zinc-300">·</span>
        <span className="font-medium text-zinc-700">★ {r.aggregate_rating ?? ''}</span>
      </div>
      {badges.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">{badges}</div>
      )}
      {cuisines.length > 0 && (
        <div className="flex flex-wrap gap-1.5">{cuisines}</div>
      )}
    </div>
  );
}
