"""
Runs the full pipeline (segmentation -> background -> 90-variable
features -> per-cell Gram voting -> overlay images) on one already
decoded RGB image. Both /analyze (single image) and /analyze-batch
(folder upload) call this one function, so results can never drift
between the two entry points.
"""
import time

import numpy as np

from .segmentation import preprocess_image, detect_background, segment_image, resize_if_large
from .classifier import classify_gram_cell
from .features import compute_all_features
from .visualize import build_result_images


def analyze_one_image(img_rgb: np.ndarray, filename: str) -> dict:
    t0 = time.time()
    img = resize_if_large(img_rgb)
    img_pre, gray = preprocess_image(img)
    masks, valid_regions = segment_image(img_pre)

    if not valid_regions:
        return {
            "filename": filename,
            "total_cells": 0,
            "message": "No cells passed the segmentation size filter.",
            "processing_time_seconds": round(time.time() - t0, 2),
        }

    background_rgb = detect_background(img, masks)

    # Full 90-variable SV1/SV2/SV3 profile.
    features = compute_all_features(img, gray, masks, valid_regions, background_rgb)
    features = {
        k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
        for k, v in features.items()
    }

    # Per-cell Gram vote (also needed to color the overlay image).
    red, green, blue = img[:, :, 0].astype(float), img[:, :, 1].astype(float), img[:, :, 2].astype(float)
    counts = {"gram_positive": 0, "gram_negative": 0, "unclear": 0}
    cells = []
    cell_labels = {}
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
    images = build_result_images(img, masks, valid_regions, cell_labels)

    return {
        "filename": filename,
        "total_cells": total,
        "counts": counts,
        "percentages": {k: round(100 * v / total, 1) for k, v in counts.items()},
        "cells": cells,
        "features": features,
        "images": images,
        "processing_time_seconds": round(time.time() - t0, 2),
    }
