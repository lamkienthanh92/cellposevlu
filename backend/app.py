"""
FastAPI service: upload a Gram-stained bright-field image, get back
the full ~90-variable per-image profile (SV1 intensity/staining, SV2
cell-wall imaging proxies, SV3 morphology + 5-vote Gram classification)
plus a per-cell breakdown.

Run locally:   uvicorn app:app --reload --port 7860
Deployed on:   Hugging Face Spaces (Docker SDK)
"""
import io
import time

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

from pipeline import config as cfg
from pipeline.segmentation import preprocess_image, detect_background, segment_image, resize_if_large
from pipeline.classifier import classify_gram_cell
from pipeline.features import compute_all_features

app = FastAPI(
    title="Automated Gram Classification API",
    description="Cellpose 2.0 segmentation + 5-vote Gram classifier + full 90-variable feature extraction",
    version=cfg.CONFIG_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {
        "status": "ok",
        "config_version": cfg.CONFIG_VERSION,
        "known_open_items": cfg.KNOWN_OPEN_ITEMS,
    }


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file (jpg/png/tiff).")

    raw = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not read image file.")

    img = resize_if_large(np.array(pil_img))

    t0 = time.time()
    img_pre, gray = preprocess_image(img)
    masks, valid_regions = segment_image(img_pre)

    if not valid_regions:
        return {
            "total_cells": 0,
            "message": "No cells passed the segmentation size filter.",
            "processing_time_seconds": round(time.time() - t0, 2),
        }

    background_rgb = detect_background(img, masks)

    # Full 90-variable SV1/SV2/SV3 profile (same schema as the
    # original Excel output, minus 'filename').
    features = compute_all_features(img, gray, masks, valid_regions, background_rgb)
    features = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                for k, v in features.items()}

    # Per-cell breakdown (for the UI bar chart + optional CSV export).
    red, green, blue = img[:, :, 0].astype(float), img[:, :, 1].astype(float), img[:, :, 2].astype(float)
    counts = {"gram_positive": 0, "gram_negative": 0, "unclear": 0}
    cells = []
    for region in valid_regions:
        cell_mask = masks == region.label
        cell_rgb = np.array([red[cell_mask].mean(), green[cell_mask].mean(), blue[cell_mask].mean()])
        label, brr = classify_gram_cell(cell_rgb, background_rgb)
        counts[label] += 1
        cells.append({
            "cell_id": int(region.label),
            "area_px": int(region.area),
            "centroid": [float(region.centroid[1]), float(region.centroid[0])],
            "classification": label,
            "blue_red_ratio": round(float(brr), 3),
        })

    total = len(valid_regions)
    elapsed = round(time.time() - t0, 2)

    return {
        "total_cells": total,
        "counts": counts,
        "percentages": {k: round(100 * v / total, 1) for k, v in counts.items()},
        "cells": cells,
        "features": features,          # full ~90-variable SV1/SV2/SV3 profile
        "classifier_parameters": {
            "v1_margin": cfg.COLOR_DISTANCE_UNCLEAR_MARGIN,
            "v2_gp": cfg.BLUE_RED_RATIO_GRAMPOS_MIN,
            "v2_gn": cfg.BLUE_RED_RATIO_GRAMNEG_MAX,
            "v3": cfg.BLUE_DARKNESS_THRESHOLD,
            "v4": cfg.RED_DARKNESS_THRESHOLD,
            "v5": cfg.CHANNEL_GAP_THRESHOLD,
        },
        "processing_time_seconds": elapsed,
    }
