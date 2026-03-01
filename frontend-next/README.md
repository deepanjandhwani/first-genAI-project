# Zomato AI Recommendations — Next.js UI

Premium Next.js UI for the restaurant recommendation API.

## Prerequisites

- Node.js 18+
- Backend running at `http://localhost:8000` (or set `NEXT_PUBLIC_API_URL`)

## Development

```bash
cd frontend-next
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The app will call the API at `http://localhost:8000` (or the URL in `NEXT_PUBLIC_API_URL`).

## Production build (served by FastAPI)

Build a static export so the FastAPI server can serve it at `/app/`:

```bash
cd frontend-next
npm install
npm run build
```

Then start the backend from the project root:

```bash
bash scripts/run_server.sh
```

Visit [http://localhost:8000/app/](http://localhost:8000/app/) to use the Next.js UI. No separate Node server is required.

## Environment

- `NEXT_PUBLIC_API_URL` — Leave unset when the UI is served from FastAPI at `/app/` (same-origin). Set to `http://localhost:8000` when running `npm run dev` so the dev server can call the API.
