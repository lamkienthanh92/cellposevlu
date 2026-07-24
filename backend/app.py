"""
FastAPI service: upload one Gram-stained bright-field image (or a
whole folder of them), get back the full ~90-variable per-image
profile (SV1 intensity/staining, SV2 cell-wall imaging proxies, SV3
morphology + 5-vote Gram classification), a per-cell breakdown, and
three overlay images (original / segmentation / Gram classification)
for visual inspection.

Endpoints:
  GET  /              health check
  POST /analyze       one image  -> one result
  POST /analyze-batch several images (folder upload) -> list of results
  POST /export-excel   list of {filename, features} -> .xlsx download
                        (90-variable sheet layout, same as the
                        standalone batch script)

Run locally:   uvicorn app:app --reload --port 7860
Deployed on:   Hugging Face Spaces (Docker SDK)
"""
import io
from typing import List

import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from PIL import Image

from pipeline import config as cfg
from pipeline.analyze import analyze_one_image
from pipeline.excel_export import build_excel_workbook

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


def _load_rgb(raw: bytes) -> np.ndarray:
    try:
        pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(400, "Could not read image file.")
    return np.array(pil_img)


def _classifier_parameters() -> dict:
    return {
        "v1_margin": cfg.COLOR_DISTANCE_UNCLEAR_MARGIN,
        "v2_gp": cfg.BLUE_RED_RATIO_GRAMPOS_MIN,
        "v2_gn": cfg.BLUE_RED_RATIO_GRAMNEG_MAX,
        "v3": cfg.BLUE_DARKNESS_THRESHOLD,
        "v4": cfg.RED_DARKNESS_THRESHOLD,
        "v5": cfg.CHANNEL_GAP_THRESHOLD,
    }


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
    img = _load_rgb(raw)
    result = analyze_one_image(img, file.filename)
    result["classifier_parameters"] = _classifier_parameters()
    return result


@app.post("/analyze-batch")
async def analyze_batch(files: List[UploadFile] = File(...)):
    """
    Accepts every file the browser's folder picker collected. Non-image
    files (e.g. .DS_Store, Thumbs.db) are silently skipped rather than
    failing the whole batch.
    """
    results = []
    for f in files:
        if not f.content_type or not f.content_type.startswith("image/"):
            continue
        raw = await f.read()
        try:
            img = _load_rgb(raw)
        except HTTPException:
            continue
        results.append(analyze_one_image(img, f.filename))

    return {
        "count": len(results),
        "results": results,
        "classifier_parameters": _classifier_parameters(),
    }


class ExportRow(BaseModel):
    filename: str
    features: dict


class ExportRequest(BaseModel):
    rows: List[ExportRow]


@app.post("/export-excel")
async def export_excel(payload: ExportRequest):
    if not payload.rows:
        raise HTTPException(400, "No rows to export.")

    records = [{"filename": r.filename, **r.features} for r in payload.rows]
    workbook_bytes = build_excel_workbook(records)

    return StreamingResponse(
        io.BytesIO(workbook_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=gram_analysis_90vars.xlsx"},
    )
