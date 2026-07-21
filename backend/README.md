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
  name `file`), get back per-cell counts and classification.

See the main repo README for how the React frontend connects to this
Space.
