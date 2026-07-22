"""
FastAPI service for the Automated Gram Classification System.

Endpoints:
  GET  /                health check
  POST /analyze          upload 1+ images -> per-image results
                          (counts, 90-variable feature profile,
                          original/segmented/gram-classified images)
  POST /export-excel     upload 1+ images -> multi-sheet .xlsx download
                          (same schema as the original Colab pipeline:
                          Full_Data, SV1/SV2/SV3, Background_Info,
                          Summary_Statistics)

Run locally:   uvicorn app:app --reload --port 7860
Deployed on:   Hugging Face Spaces (Docker SDK)
"""
import io
import time
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image

from pipeline import config as cfg
from pipeline.segmentation import preprocess_image, detect_background, segment_image, resize_if_large
from pipeline.classifier import classify_gram_cell
from pipeline.features import compute_all_features
from pipeline.visualize import render_original, render_segmentation_overlay, render_gram_overlay

app = FastAPI(
    title="Automated Gram Classification API",
    description="Cellpose 2.0 segmentation + 5-vote Gram classifier, batch mode",
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


def _load_image(upload_bytes, filename):
    try:
        pil_img = Image.open(io.BytesIO(upload_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(400, f"Could not read image file: {filename}")
    return resize_if_large(np.array(pil_img))


def _process_one(img, filename):
    """
    Runs the full pipeline on a single already-loaded RGB image.
    Returns a dict with counts, percentages, 90-var features, and the
    3 rendered images (base64 PNG), or an 'empty' result if no cells
    passed the segmentation/area filter.
    """
    t0 = time.time()
    img_pre, gray = preprocess_image(img)
    masks, valid_regions = segment_image(img_pre, gray)

    if not valid_regions:
        return {
            "filename": filename,
            "total_cells": 0,
            "message": "No cells passed the segmentation size filter.",
            "processing_time_seconds": round(time.time() - t0, 2),
            "images": {"original": render_original(img), "segmented": None, "gram_classified": None},
        }

    background_rgb = detect_background(img, masks)
    features = compute_all_features(img, gray, masks, valid_regions, background_rgb)
    features = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                for k, v in features.items()}

    red, green, blue = img[:, :, 0].astype(float), img[:, :, 1].astype(float), img[:, :, 2].astype(float)
    counts = {"gram_positive": 0, "gram_negative": 0, "unclear": 0}
    cell_labels = {}
    cells = []
    for region in valid_regions:
        cell_mask = masks == region.label
        cell_rgb = np.array([red[cell_mask].mean(), green[cell_mask].mean(), blue[cell_mask].mean()])
        label, brr = classify_gram_cell(cell_rgb, background_rgb)
        counts[label] += 1
        cell_labels[region.label] = label
        cells.append({
            "cell_id": int(region.label),
            "area_px": int(region.area),
            "centroid": [float(region.centroid[1]), float(region.centroid[0])],
            "classification": label,
            "blue_red_ratio": round(float(brr), 3),
        })

    total = len(valid_regions)

    images = {
        "original": render_original(img),
        "segmented": render_segmentation_overlay(img, masks, valid_regions),
        "gram_classified": render_gram_overlay(img, masks, valid_regions, cell_labels),
    }

    return {
        "filename": filename,
        "total_cells": total,
        "counts": counts,
        "percentages": {k: round(100 * v / total, 1) for k, v in counts.items()},
        "cells": cells,
        "features": features,
        "images": images,
        "classifier_parameters": {
            "v1_margin": cfg.COLOR_DISTANCE_UNCLEAR_MARGIN,
            "v2_gp": cfg.BLUE_RED_RATIO_GRAMPOS_MIN,
            "v2_gn": cfg.BLUE_RED_RATIO_GRAMNEG_MAX,
            "v3": cfg.BLUE_DARKNESS_THRESHOLD,
            "v4": cfg.RED_DARKNESS_THRESHOLD,
            "v5": cfg.CHANNEL_GAP_THRESHOLD,
        },
        "processing_time_seconds": round(time.time() - t0, 2),
    }


@app.post("/analyze")
async def analyze(files: List[UploadFile] = File(...)):
    results = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            results.append({"filename": f.filename, "total_cells": 0,
                             "message": "Not an image file, skipped."})
            continue
        raw = await f.read()
        img = _load_image(raw, f.filename)
        results.append(_process_one(img, f.filename))
    return {"results": results}


@app.post("/export-excel")
async def export_excel(files: List[UploadFile] = File(...)):
    """
    Re-runs the pipeline on the uploaded images and returns a
    multi-sheet .xlsx, matching the original Colab pipeline's layout:
    Full_Data, SV1_Intensity_30vars, SV2_CellWall_30vars,
    SV3_Morphology_30vars, Background_Info, Summary_Statistics.
    """
    rows = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        raw = await f.read()
        img = _load_image(raw, f.filename)
        result = _process_one(img, f.filename)

        row = {"filename": result["filename"]}
        if result.get("features"):
            row.update(result["features"])
        rows.append(row)

    if not rows:
        raise HTTPException(400, "No valid images to export.")

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Full_Data", index=False)
        for prefix, sheet in [
            ("sv1_", "SV1_Intensity_30vars"),
            ("sv2_", "SV2_CellWall_30vars"),
            ("sv3_", "SV3_Morphology_30vars"),
        ]:
            cols = ["filename"] + [c for c in df.columns if c.startswith(prefix)]
            df[cols].to_excel(writer, sheet_name=sheet, index=False)

        bg_cols = [c for c in ["filename", "bg_r", "bg_g", "bg_b",
                                "sv1_blue_bg_mean", "sv1_red_bg_mean"] if c in df.columns]
        df[bg_cols].to_excel(writer, sheet_name="Background_Info", index=False)

        valid_df = df[df.get("sv1_valid_cells", 0) > 0] if "sv1_valid_cells" in df.columns else df
        if len(valid_df) > 0:
            metrics = [
                ("Total Images", len(df)),
                ("Images with Cells", len(valid_df)),
                ("Avg Cells/Image", valid_df.get("sv1_valid_cells", pd.Series([0])).mean()),
                ("Avg Gram+ %", valid_df.get("sv3_gram_pos_pct", pd.Series([0])).mean()),
                ("Avg Gram- %", valid_df.get("sv3_gram_neg_pct", pd.Series([0])).mean()),
                ("Avg Area (um2)", valid_df.get("sv3_mean_area_um2", pd.Series([0])).mean()),
                ("Avg Circularity", valid_df.get("sv3_mean_circularity", pd.Series([0])).mean()),
                ("Avg Blue Intensity", valid_df.get("sv1_blue_mean", pd.Series([0])).mean()),
                ("Avg Red Intensity", valid_df.get("sv1_red_mean", pd.Series([0])).mean()),
                ("Avg Wall Thickness (um)", valid_df.get("sv2_wall_thickness_mean", pd.Series([0])).mean()),
                ("Avg Membrane Integrity %", valid_df.get("sv2_membrane_integrity_score", pd.Series([0])).mean()),
            ]
            pd.DataFrame(metrics, columns=["Metric", "Value"]).to_excel(
                writer, sheet_name="Summary_Statistics", index=False
            )

    buf.seek(0)
    fname = f"gram_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
