"""
Full per-image feature extraction — SV1 (intensity/staining, 30 vars),
SV2 (cell-wall imaging proxies, 30 vars), SV3 (morphology + Gram
classification outputs, 30 vars). Logic ported unchanged from
CELLPOSE_CODE.docx; only reads parameters from config.py instead of
hardcoded module-level constants.
"""
import random

import numpy as np
import cv2
from scipy import ndimage

from . import config as cfg
from .classifier import classify_gram_cell

TEXTURE_SAMPLE_SIZE = 20
PIXEL_SIZE = cfg.SEG.get("pixel_size_um", 0.1)
PIXEL_AREA = PIXEL_SIZE ** 2


def calculate_snr(cell_intensity, background):
    if len(background) > 0 and background.std() > 0:
        return cell_intensity.mean() / background.std()
    return 0


def calculate_shannon_diversity(values):
    if len(values) == 0:
        return 0
    hist, _ = np.histogram(values, bins=5)
    hist = hist[hist > 0]
    if len(hist) == 0:
        return 0
    proportions = hist / hist.sum()
    return -np.sum(proportions * np.log(proportions))


_TEXTURE_KEYS = ["mean_texture_roughness", "std_texture_roughness",
                 "mean_texture_contrast", "texture_uniformity",
                 "texture_diversity", "texture_range"]


def analyze_texture_sampled(gray, masks, valid_regions, sample_size=TEXTURE_SAMPLE_SIZE):
    if len(valid_regions) == 0:
        return {k: 0 for k in _TEXTURE_KEYS}
    texture_map = ndimage.generic_filter(gray, np.std, size=5)
    sampled = random.sample(valid_regions, min(sample_size, len(valid_regions)))
    texture_values, contrast_values = [], []
    for region in sampled:
        cell_mask = masks == region.label
        texture_values.append(np.mean(texture_map[cell_mask]))
        contrast_values.append(np.std(gray[cell_mask]))
    if not texture_values:
        return {k: 0 for k in _TEXTURE_KEYS}
    return {
        "mean_texture_roughness": np.mean(texture_values),
        "std_texture_roughness": np.std(texture_values),
        "mean_texture_contrast": np.mean(contrast_values),
        "texture_uniformity": 100 / (1 + np.std(texture_values)),
        "texture_diversity": calculate_shannon_diversity(texture_values),
        "texture_range": np.max(texture_values) - np.min(texture_values),
    }


_EDGE_KEYS = ["mean_edge_intensity", "mean_edge_sharpness",
              "std_edge_intensity", "edge_uniformity", "mean_boundary_contrast"]


def analyze_edges_cached(gray, masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in _EDGE_KEYS}
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.sqrt(gx ** 2 + gy ** 2)
    edge_int, edge_sharp, bnd_contrast = [], [], []
    for region in valid_regions:
        cell_mask = masks == region.label
        eroded = ndimage.binary_erosion(cell_mask, iterations=1)
        boundary = cell_mask & ~eroded
        if np.sum(boundary) < 5:
            continue
        edge_int.append(np.mean(grad[boundary]))
        edge_sharp.append(np.percentile(grad[boundary], 75))
        dilated = ndimage.binary_dilation(cell_mask, iterations=2)
        ring = dilated & ~cell_mask
        if np.sum(ring) > 0:
            bnd_contrast.append(abs(np.mean(gray[cell_mask]) - np.mean(gray[ring])))
    if not edge_int:
        return {k: 0 for k in _EDGE_KEYS}
    mean_ei = np.mean(edge_int)
    return {
        "mean_edge_intensity": mean_ei,
        "mean_edge_sharpness": np.mean(edge_sharp),
        "std_edge_intensity": np.std(edge_int),
        "edge_uniformity": 100 - (np.std(edge_int) / mean_ei * 100) if mean_ei > 0 else 0,
        "mean_boundary_contrast": np.mean(bnd_contrast) if bnd_contrast else 0,
    }


_WALL_KEYS = ["mean_wall_thickness_estimate", "median_wall_thickness_estimate",
              "std_wall_thickness", "cv_wall_thickness", "max_wall_thickness"]


def analyze_wall_thickness_fast(masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in _WALL_KEYS}
    dist_all = ndimage.distance_transform_edt(masks > 0)
    thicknesses = [
        np.mean(dist_all[masks == r.label]) * PIXEL_SIZE
        for r in valid_regions if np.sum(masks == r.label) > 0
    ]
    if not thicknesses:
        return {k: 0 for k in _WALL_KEYS}
    mt = np.mean(thicknesses)
    return {
        "mean_wall_thickness_estimate": mt,
        "median_wall_thickness_estimate": np.median(thicknesses),
        "std_wall_thickness": np.std(thicknesses),
        "cv_wall_thickness": (np.std(thicknesses) / mt * 100) if mt > 0 else 0,
        "max_wall_thickness": np.max(thicknesses),
    }


_MEMBRANE_KEYS = ["mean_intensity_uniformity", "mean_shape_regularity",
                  "membrane_integrity_score", "pct_intact_cells", "fragmentation_index"]


def analyze_membrane_integrity(gray, masks, valid_regions):
    if len(valid_regions) == 0:
        return {k: 0 for k in _MEMBRANE_KEYS}
    uniformities, regularities, intact = [], [], 0
    for region in valid_regions:
        cell_mask = masks == region.label
        cell_pixels = gray[cell_mask]
        if len(cell_pixels) > 10:
            cv = (np.std(cell_pixels) / np.mean(cell_pixels) * 100) if np.mean(cell_pixels) > 0 else 100
            u = 100 - min(cv, 100)
            uniformities.append(u)
        else:
            u = 0
        circ = (4 * np.pi * region.area) / (region.perimeter ** 2) if region.perimeter > 0 else 0
        reg = circ * region.solidity
        regularities.append(reg)
        if u > 70 and reg > 0.7:
            intact += 1
    n = len(valid_regions)
    return {
        "mean_intensity_uniformity": np.mean(uniformities) if uniformities else 0,
        "mean_shape_regularity": np.mean(regularities),
        "membrane_integrity_score": (np.mean(uniformities) + np.mean(regularities) * 100) / 2 if uniformities else 0,
        "pct_intact_cells": (intact / n * 100) if n > 0 else 0,
        "fragmentation_index": ((n - intact) / n * 100) if n > 0 else 0,
    }


_PEPTIDO_KEYS = ["mean_cv_retention", "median_cv_retention",
                 "std_cv_retention", "cv_retention_range", "peptidoglycan_score"]


def analyze_peptidoglycan(img, masks, valid_regions, background_rgb):
    if len(valid_regions) == 0:
        return {k: 0 for k in _PEPTIDO_KEYS}
    blue = img[:, :, 2]
    bg_b = background_rgb[2]
    cv_retentions = [bg_b - np.mean(blue[masks == r.label]) for r in valid_regions]
    mean_ret = np.mean(cv_retentions)
    return {
        "mean_cv_retention": mean_ret,
        "median_cv_retention": np.median(cv_retentions),
        "std_cv_retention": np.std(cv_retentions),
        "cv_retention_range": np.max(cv_retentions) - np.min(cv_retentions),
        "peptidoglycan_score": np.clip(mean_ret * 3, 0, 100),
    }


def compute_all_features(img_original, gray, masks, valid_regions, background_rgb):
    """
    Returns the full ~90-variable dict (SV1/SV2/SV3), matching the
    column layout of the original Excel output (minus 'filename',
    which the caller adds).
    """
    n_cells = int(masks.max())
    n_valid = len(valid_regions)

    red = img_original[:, :, 0].astype(float)
    green = img_original[:, :, 1].astype(float)
    blue = img_original[:, :, 2].astype(float)
    cell_mask_all = masks > 0
    background_mask = masks == 0

    # --- SV1: Intensity & Staining ---
    blue_cells = blue[cell_mask_all]
    red_cells = red[cell_mask_all]
    blue_bg = blue[background_mask]
    red_bg = red[background_mask]

    sv1_blue_mean = np.mean(blue_cells)
    sv1_blue_std = np.std(blue_cells)
    sv1_blue_median = np.median(blue_cells)
    sv1_blue_cv_pct = sv1_blue_std / sv1_blue_mean * 100 if sv1_blue_mean > 0 else 0
    sv1_blue_min = np.min(blue_cells)
    sv1_blue_max = np.max(blue_cells)
    sv1_red_mean = np.mean(red_cells)
    sv1_red_std = np.std(red_cells)
    sv1_red_median = np.median(red_cells)
    sv1_red_cv_pct = sv1_red_std / sv1_red_mean * 100 if sv1_red_mean > 0 else 0
    sv1_red_min = np.min(red_cells)
    sv1_red_max = np.max(red_cells)

    sv1_blue_bg_mean = np.mean(blue_bg) if len(blue_bg) > 0 else 0
    sv1_blue_bg_std = np.std(blue_bg) if len(blue_bg) > 0 else 0
    sv1_red_bg_mean = np.mean(red_bg) if len(red_bg) > 0 else 0
    sv1_red_bg_std = np.std(red_bg) if len(red_bg) > 0 else 0
    sv1_bg_noise = (sv1_blue_bg_std + sv1_red_bg_std) / 2

    sv1_blue_red_ratio = sv1_blue_mean / sv1_red_mean if sv1_red_mean > 0 else 0
    sv1_contrast_ratio = (sv1_blue_mean - sv1_red_mean) / (sv1_blue_mean + sv1_red_mean + 1e-9)
    sv1_color_separation = abs(sv1_blue_mean - sv1_red_mean) / (sv1_blue_mean + sv1_red_mean + 1e-9)
    sv1_staining_quality = sv1_blue_mean / (sv1_blue_std + sv1_red_std + 1e-9)
    sv1_dynamic_range = (sv1_blue_max - sv1_blue_min + sv1_red_max - sv1_red_min) / 2
    sv1_intensity_balance = min(sv1_blue_mean, sv1_red_mean) / max(sv1_blue_mean, sv1_red_mean + 1e-9)
    sv1_blue_snr = calculate_snr(blue_cells, blue_bg)
    sv1_red_snr = calculate_snr(red_cells, red_bg)
    sv1_combined_snr = (sv1_blue_snr + sv1_red_snr) / 2
    sv1_signal_clarity = (sv1_blue_mean + sv1_red_mean) / (sv1_blue_std + sv1_red_std + 1e-9)
    sv1_noise_ratio = sv1_bg_noise / ((sv1_blue_mean + sv1_red_mean) / 2 + 1e-9)
    sv1_bg_uniformity = 100 - sv1_bg_noise

    # --- SV2: Cell Wall (imaging proxies) ---
    tex = analyze_texture_sampled(gray, masks, valid_regions)
    edg = analyze_edges_cached(gray, masks, valid_regions)
    wth = analyze_wall_thickness_fast(masks, valid_regions)
    mig = analyze_membrane_integrity(gray, masks, valid_regions)
    pep = analyze_peptidoglycan(img_original, masks, valid_regions, background_rgb)

    sv2_wall_quality_score = (edg["mean_edge_sharpness"] / 10 + mig["membrane_integrity_score"] / 2 + pep["peptidoglycan_score"]) / 3
    sv2_wall_uniformity = (edg["edge_uniformity"] + mig["mean_intensity_uniformity"]) / 2
    sv2_wall_strength_index = (pep["peptidoglycan_score"] + mig["pct_intact_cells"]) / 2
    sv2_permeability = 100 - sv2_wall_strength_index

    # --- SV3: Morphology & Gram Classification ---
    areas_um = [r.area * PIXEL_AREA for r in valid_regions]
    circularities = [(4 * np.pi * r.area) / (r.perimeter ** 2) if r.perimeter > 0 else 0 for r in valid_regions]
    aspect_ratios = [r.major_axis_length / r.minor_axis_length if r.minor_axis_length > 0 else 1 for r in valid_regions]
    roundnesses = [(4 * r.area) / (np.pi * r.major_axis_length ** 2) if r.major_axis_length > 0 else 1 for r in valid_regions]
    solidities = [r.solidity for r in valid_regions]
    ferets = [r.feret_diameter_max * PIXEL_SIZE for r in valid_regions]

    image_area_um = img_original.shape[0] * img_original.shape[1] * PIXEL_AREA
    debris_count = sum(1 for a in areas_um if a < 0.5)
    intact_count = n_valid - debris_count

    gram_pos = gram_neg = unclear = 0
    for region in valid_regions:
        cell_mask = masks == region.label
        cell_rgb = np.array([np.mean(red[cell_mask]), np.mean(green[cell_mask]), np.mean(blue[cell_mask])])
        label, _ = classify_gram_cell(cell_rgb, background_rgb)
        if label == "gram_positive":
            gram_pos += 1
        elif label == "gram_negative":
            gram_neg += 1
        else:
            unclear += 1

    sv3_mean_area = np.mean(areas_um)
    sv3_std_area = np.std(areas_um)

    return {
        # SV1 — Intensity & Staining (30 vars)
        "sv1_total_cells": n_cells, "sv1_valid_cells": n_valid,
        "sv1_detection_rate": n_valid / n_cells * 100 if n_cells > 0 else 0,
        "sv1_blue_mean": sv1_blue_mean, "sv1_blue_std": sv1_blue_std,
        "sv1_blue_median": sv1_blue_median, "sv1_blue_cv_pct": sv1_blue_cv_pct,
        "sv1_blue_min": sv1_blue_min, "sv1_blue_max": sv1_blue_max,
        "sv1_red_mean": sv1_red_mean, "sv1_red_std": sv1_red_std,
        "sv1_red_median": sv1_red_median, "sv1_red_cv_pct": sv1_red_cv_pct,
        "sv1_red_min": sv1_red_min, "sv1_red_max": sv1_red_max,
        "sv1_blue_red_ratio": sv1_blue_red_ratio,
        "sv1_contrast_ratio": sv1_contrast_ratio,
        "sv1_color_separation": sv1_color_separation,
        "sv1_staining_quality": sv1_staining_quality,
        "sv1_dynamic_range": sv1_dynamic_range,
        "sv1_intensity_balance": sv1_intensity_balance,
        "sv1_blue_snr": sv1_blue_snr, "sv1_red_snr": sv1_red_snr,
        "sv1_combined_snr": sv1_combined_snr,
        "sv1_signal_clarity": sv1_signal_clarity,
        "sv1_noise_ratio": sv1_noise_ratio,
        "sv1_blue_bg_mean": sv1_blue_bg_mean, "sv1_blue_bg_std": sv1_blue_bg_std,
        "sv1_red_bg_mean": sv1_red_bg_mean, "sv1_red_bg_std": sv1_red_bg_std,
        "sv1_bg_noise_level": sv1_bg_noise, "sv1_bg_uniformity": sv1_bg_uniformity,
        # SV2 — Cell Wall imaging proxies (30 vars)
        "sv2_texture_contrast": tex["mean_texture_contrast"],
        "sv2_texture_roughness": tex["mean_texture_roughness"],
        "sv2_texture_std": tex["std_texture_roughness"],
        "sv2_texture_uniformity": tex["texture_uniformity"],
        "sv2_texture_diversity": tex["texture_diversity"],
        "sv2_texture_range": tex["texture_range"],
        "sv2_edge_intensity": edg["mean_edge_intensity"],
        "sv2_edge_sharpness": edg["mean_edge_sharpness"],
        "sv2_edge_std": edg["std_edge_intensity"],
        "sv2_edge_uniformity": edg["edge_uniformity"],
        "sv2_boundary_contrast": edg["mean_boundary_contrast"],
        "sv2_wall_thickness_mean": wth["mean_wall_thickness_estimate"],
        "sv2_wall_thickness_median": wth["median_wall_thickness_estimate"],
        "sv2_wall_thickness_std": wth["std_wall_thickness"],
        "sv2_wall_thickness_cv": wth["cv_wall_thickness"],
        "sv2_wall_thickness_max": wth["max_wall_thickness"],
        "sv2_intensity_uniformity": mig["mean_intensity_uniformity"],
        "sv2_shape_regularity": mig["mean_shape_regularity"],
        "sv2_membrane_integrity_score": mig["membrane_integrity_score"],
        "sv2_pct_intact_cells": mig["pct_intact_cells"],
        "sv2_fragmentation_index": mig["fragmentation_index"],
        "sv2_cv_retention_mean": pep["mean_cv_retention"],
        "sv2_cv_retention_median": pep["median_cv_retention"],
        "sv2_cv_retention_std": pep["std_cv_retention"],
        "sv2_cv_retention_range": pep["cv_retention_range"],
        "sv2_peptidoglycan_score": pep["peptidoglycan_score"],
        "sv2_wall_quality_score": sv2_wall_quality_score,
        "sv2_wall_uniformity": sv2_wall_uniformity,
        "sv2_wall_strength_index": sv2_wall_strength_index,
        "sv2_permeability_estimate": sv2_permeability,
        # SV3 — Morphology & Gram Classification (30 vars)
        "sv3_total_cells": n_cells, "sv3_valid_cells": n_valid,
        "sv3_cell_density_per_um2": n_valid / image_area_um,
        "sv3_cell_coverage_pct": sum(areas_um) / image_area_um * 100,
        "sv3_mean_area_um2": sv3_mean_area,
        "sv3_median_area_um2": np.median(areas_um),
        "sv3_std_area_um2": sv3_std_area,
        "sv3_cv_size_pct": sv3_std_area / sv3_mean_area * 100 if sv3_mean_area > 0 else 0,
        "sv3_min_area_um2": np.min(areas_um), "sv3_max_area_um2": np.max(areas_um),
        "sv3_size_range_um2": np.max(areas_um) - np.min(areas_um),
        "sv3_mean_circularity": np.mean(circularities),
        "sv3_std_circularity": np.std(circularities),
        "sv3_mean_roundness": np.mean(roundnesses),
        "sv3_mean_solidity": np.mean(solidities),
        "sv3_mean_aspect_ratio": np.mean(aspect_ratios),
        "sv3_std_aspect_ratio": np.std(aspect_ratios),
        "sv3_mean_feret_diam_um": np.mean(ferets),
        "sv3_pct_elongated_cells": sum(1 for ar in aspect_ratios if ar > 3) / len(aspect_ratios) * 100,
        "sv3_elongation_index": (np.mean(aspect_ratios) - 1) * 100,
        "sv3_shape_diversity": calculate_shannon_diversity(circularities),
        "sv3_size_heterogeneity": sv3_std_area / sv3_mean_area * 100 if sv3_mean_area > 0 else 0,
        "sv3_morphology_score": (np.mean(circularities) + np.mean(roundnesses) + np.mean(solidities)) / 3,
        "sv3_uniformity_index": 100 / (1 + sv3_std_area / sv3_mean_area * 100) if sv3_mean_area > 0 else 0,
        "sv3_lysis_pct": debris_count / n_valid * 100 if n_valid > 0 else 0,
        "sv3_debris_count": debris_count, "sv3_intact_count": intact_count,
        "sv3_gram_pos_count": gram_pos, "sv3_gram_neg_count": gram_neg,
        "sv3_unclear_count": unclear,
        "sv3_gram_pos_pct": gram_pos / n_valid * 100 if n_valid > 0 else 0,
        "sv3_gram_neg_pct": gram_neg / n_valid * 100 if n_valid > 0 else 0,
        "sv3_gram_mixed_pct": unclear / n_valid * 100 if n_valid > 0 else 0,
        "bg_r": float(background_rgb[0]), "bg_g": float(background_rgb[1]), "bg_b": float(background_rgb[2]),
    }
