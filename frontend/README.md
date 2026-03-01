# Restaurant Recommendations – React UI

## Build for production (served by FastAPI)

From the project root:

```bash
cd frontend
npm install
npm run build
cd ..
```

Then start the API; the React app will be served at **http://localhost:8000/app/**.

```bash
bash scripts/run_server.sh
```

## Development (React dev server + API proxy)

Terminal 1 – API:

```bash
.venv/bin/python -m uvicorn phase5.display.api:create_app --factory --host 0.0.0.0 --port 8000
```

Terminal 2 – React (with proxy to API):

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** – the Place dropdown and recommendations use the API on port 8000.
