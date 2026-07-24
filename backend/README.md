---
title: Gram Stain Classifier API
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Gram Stain Classifier — API

FastAPI backend for the Automated Gram Classification System
(Cellpose 2.0 + 5-vote classifier). Deployed here as a Hugging Face
Space using the Docker SDK.

- `GET /` — health check, also returns the currently loaded
  classifier config version and any open validation caveats.
- `POST /analyze` — upload an image (`multipart/form-data`, field
  name `file`), get back per-cell counts, classification, the full
  90-variable profile, and three overlay images (original /
  segmentation / Gram classification) as base64 PNGs.
- `POST /analyze-batch` — upload several images at once (`multipart/
  form-data`, field name `files`, repeated), get back the same result
  shape for each image.
- `POST /export-excel` — JSON body `{ "rows": [{ "filename", "features" }] }`
  (the features already returned by `/analyze` or `/analyze-batch`) →
  streams back a multi-sheet `.xlsx` (90 variables per image).

See the main repo README for how the React frontend connects to this
Space.
