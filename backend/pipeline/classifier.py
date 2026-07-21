"""
Five-criterion voting classifier for per-cell Gram-phenotype
classification. Logic identical to the original pipeline
(CELLPOSE_CODE.docx); parameters are the corrected grid-search
optimum, loaded from classifier_config.json via config.py.
"""
import numpy as np
from . import config as cfg


def classify_gram_cell(cell_rgb, background_rgb):
    """
    Returns (label, blue_red_ratio) where label is one of
    'gram_positive', 'gram_negative', 'unclear'.
    """
    cell_r, cell_g, cell_b = cell_rgb

    # Vote 1: Euclidean RGB distance to reference prototypes (weight=2)
    dist_to_grampos = np.linalg.norm(cell_rgb - cfg.GRAM_POS_REF_RGB)
    dist_to_gramneg = np.linalg.norm(cell_rgb - cfg.GRAM_NEG_REF_RGB)

    # Vote 2: Blue/Red ratio (weight=1)
    blue_red_ratio = cell_b / (cell_r + 1)

    # Votes 3-4: Channel darkness relative to background
    bg_b = background_rgb[2]
    bg_r = background_rgb[0]
    blue_darkness_pct = (bg_b - cell_b) / bg_b if bg_b > 0 else 0
    red_darkness_pct = (bg_r - cell_r) / bg_r if bg_r > 0 else 0

    votes_pos = 0
    votes_neg = 0

    # Vote 1 (weight=2)
    if dist_to_grampos < dist_to_gramneg - cfg.COLOR_DISTANCE_UNCLEAR_MARGIN:
        votes_pos += 2
    elif dist_to_gramneg < dist_to_grampos - cfg.COLOR_DISTANCE_UNCLEAR_MARGIN:
        votes_neg += 2

    # Vote 2 (weight=1)
    if blue_red_ratio > cfg.BLUE_RED_RATIO_GRAMPOS_MIN:
        votes_pos += 1
    elif blue_red_ratio < cfg.BLUE_RED_RATIO_GRAMNEG_MAX:
        votes_neg += 1

    # Vote 3 (weight=1)
    if blue_darkness_pct >= cfg.BLUE_DARKNESS_THRESHOLD:
        votes_pos += 1

    # Vote 4 (weight=1)
    if red_darkness_pct >= cfg.RED_DARKNESS_THRESHOLD:
        votes_neg += 1

    # Vote 5 (weight=1)
    if cell_b < cell_r - cfg.CHANNEL_GAP_THRESHOLD:
        votes_pos += 1
    elif cell_r < cell_b - cfg.CHANNEL_GAP_THRESHOLD:
        votes_neg += 1

    if votes_pos > votes_neg:
        return "gram_positive", blue_red_ratio
    elif votes_neg > votes_pos:
        return "gram_negative", blue_red_ratio
    else:
        return "unclear", blue_red_ratio
