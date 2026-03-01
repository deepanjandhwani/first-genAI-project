import { RecommendationForm } from '@/components/RecommendationForm';

export default function Home() {
  return (
    <div className="min-h-screen">
      <header className="bg-[#e23744] text-white py-5 px-6 text-center shadow-sm">
        <div className="inline-flex items-center gap-2 text-xl font-bold tracking-tight">
          <svg className="w-7 h-7" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
            <path d="M11 9H9V2H7v7H5V2H3v7c0 2.12 1.66 3.84 3.75 3.97V22h2.5v-9.03C11.34 12.84 13 11.12 13 9V2h-2v7zm5-3v8h2.5v8H21V2c-2.76 0-5 2.24-5 4z" />
          </svg>
          ZOMATO
        </div>
        <p className="text-sm opacity-95 mt-1">AI Restaurant Recommendation Platform</p>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
        <RecommendationForm />
      </main>
    </div>
  );
}
