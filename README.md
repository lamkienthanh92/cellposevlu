# Automated Gram Classification System

Cellpose 2.0 segmentation + 5-vote classifier, wrapped in a web app.
Supports a single image or a whole folder of images, exports the full
90-variable profile to Excel, and lets you click any result to inspect
its original / segmentation / Gram-classification overlay images.

- `backend/` — FastAPI service (Cellpose + classifier + Excel export),
  deployed as a Hugging Face Space using the Docker SDK.
- `frontend/` — React (Vite) app. Choose one image or an entire folder,
  get back per-cell counts, classification, and the full 90-variable
  profile per image. Can be hosted anywhere static (GitHub Pages,
  Vercel, Netlify) since it only calls the backend API.

## Features

- **Single image or folder input** — a mode toggle switches the
  upload panel between a single drag-and-drop image and a folder
  picker (`webkitdirectory`) that picks up every JPG/PNG/TIFF inside.
- **Per-image visual inspection** — every processed image (single or
  batch) returns three overlay images: the original, the segmentation
  contours, and the Gram-classification contours (colored by vote
  outcome). In batch mode, click any card in the results grid to open
  these in a modal alongside that image's own 90-variable breakdown.
- **Excel export (90 variables)** — a "Xuất Excel" button (single
  image or whole batch) calls `POST /export-excel`, which returns a
  multi-sheet workbook (`Full_Data`, `SV1_Intensity_30vars`,
  `SV2_CellWall_30vars`, `SV3_Morphology_30vars`, `Background_Info`,
  `Summary_Statistics`) — the same layout as the original standalone
  batch script. No re-processing: it reuses the features already
  computed by `/analyze` or `/analyze-batch`.

## How the pieces fit together

```
 ┌──────────────┐   POST /analyze            ┌───────────────────────┐
 │   React app   │   POST /analyze-batch      │   FastAPI (HF Space)  │
 │ (GitHub Pages │ ─────────────────────────▶ │  Cellpose 2.0 +       │
 │  / Netlify)   │   image file(s)             │  5-vote classifier    │
 │               │ ◀───────────────────────── │  + overlay images     │
 │               │   JSON result(s)            └───────────────────────┘
 │               │
 │               │   POST /export-excel  (features already in hand)
 │               │ ─────────────────────────▶  same FastAPI service
 │               │ ◀───────────────────────── .xlsx download
 └──────────────┘
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

## API endpoints

- `GET /` — health check + config version + any open validation caveats.
- `POST /analyze` — one image (`multipart/form-data`, field `file`) →
  one result (counts, 90-variable `features`, overlay `images`).
- `POST /analyze-batch` — several images (`multipart/form-data`, field
  `files`, repeated) → `{ count, results: [...] }`, one entry per image
  in the same shape as `/analyze`. Non-image files picked up by the
  folder selector (e.g. `.DS_Store`) are skipped silently.
- `POST /export-excel` — JSON body `{ "rows": [{ "filename", "features" }, ...] }`
  → streams back the `.xlsx` workbook described above.

## Classifier parameters

Current parameters (`backend/classifier_config.json`) reflect the
corrected grid-search optimum — see `known_open_items` in that file
for what's still pending re-validation (Phase 2 E. coli specificity
test, Table 2 stratification) before these are final for publication.
