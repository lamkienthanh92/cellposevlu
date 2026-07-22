"""
Loads classifier + segmentation parameters from classifier_config.json
so the pipeline and the config file can never drift apart.
"""
import json
import os
import numpy as np

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "classifier_config.json")

with open(_CONFIG_PATH) as f:
    _CFG = json.load(f)

# --- segmentation ---
SEG = _CFG["segmentation"]
CELLPOSE_MODEL = "cyto2"
DIAMETER_PX = SEG["diameter_px"]
FLOW_THRESHOLD = SEG["flow_threshold"]
CELLPROB_THRESHOLD = SEG["cellprob_threshold"]
MIN_CELL_AREA_PX = SEG["min_cell_area_px"]
MAX_CELL_AREA_PX = SEG["max_cell_area_px"]

# --- preprocessing ---
CLAHE_CLIP_LIMIT = _CFG["preprocessing"]["clahe_clip_limit"]

# --- classifier ---
CLF = _CFG["classifier"]
GRAM_POS_REF_RGB = np.array(CLF["reference_prototypes_rgb"]["gram_positive"])
GRAM_NEG_REF_RGB = np.array(CLF["reference_prototypes_rgb"]["gram_negative"])

_P = CLF["parameters"]
COLOR_DISTANCE_UNCLEAR_MARGIN = _P["v1_color_distance_margin"]["value"]
BLUE_RED_RATIO_GRAMPOS_MIN = _P["v2_gp_blue_red_ratio_min"]["value"]
BLUE_RED_RATIO_GRAMNEG_MAX = _P["v2_gn_blue_red_ratio_max"]["value"]
BLUE_DARKNESS_THRESHOLD = _P["v3_blue_darkness_threshold"]["value"]
RED_DARKNESS_THRESHOLD = _P["v4_red_darkness_threshold"]["value"]
CHANNEL_GAP_THRESHOLD = _P["v5_channel_gap_threshold"]["value"]

CONFIG_VERSION = _CFG.get("version", "unknown")
KNOWN_OPEN_ITEMS = _CFG.get("known_open_items", [])
