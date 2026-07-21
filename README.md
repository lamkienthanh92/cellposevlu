# Automated Gram Classification System

Cellpose 2.0 segmentation + 5-vote classifier, wrapped in a web app.

- `backend/` — FastAPI service (Cellpose + classifier), deployed as a
  Hugging Face Space using the Docker SDK.
- `frontend/` — React (Vite) app. Upload a Gram-stained bright-field
  image, get back per-cell counts and classification. Can be hosted
  anywhere static (GitHub Pages, Vercel, Netlify) since it only calls
  the backend API.

## How the pieces fit together

```
 ┌──────────────┐        POST /analyze         ┌───────────────────────┐
 │   React app   │ ───────────────────────────▶ │   FastAPI (HF Space)  │
 │ (GitHub Pages │        image file             │  Cellpose 2.0 +       │
 │  or similar)  │ ◀─────────────────────────── │  5-vote classifier     │
 └──────────────┘        JSON result             └───────────────────────┘
```

## Quick start

### 1. Backend (local test before deploying to Hugging Face)

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 7860
```

### 2. Deploy backend to Hugging Face Spaces

1. Create a new Space → SDK: **Docker** → hardware: CPU basic (free) is
   enough; upgrade to a GPU tier later if needed.
2. Push the contents of `backend/` to the Space's git repo (it just
   needs the `Dockerfile` at the root of the Space).
3. Note the Space's public URL, e.g. `https://<user>-<space>.hf.space`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env      # set VITE_API_URL to your Space URL
npm run dev
```

Build for deployment with `npm run build`; the `dist/` folder is what
you publish to GitHub Pages / Vercel / Netlify.

## Classifier parameters

Current parameters (`backend/classifier_config.json`) reflect the
corrected grid-search optimum — see `known_open_items` in that file
for what's still pending re-validation (Phase 2 E. coli specificity
test, Table 2 stratification) before these are final for publication.
