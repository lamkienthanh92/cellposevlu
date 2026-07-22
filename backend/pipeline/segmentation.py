"""
Cellpose 2.0 segmentation + background estimation.
Extracted from the original CELLPOSE_CODE.docx pipeline, unchanged.
"""
import cv2
import numpy as np
from skimage import exposure
from cellpose import models

from . import config as cfg

_model = None


def get_model():
    """Load the Cellpose model once and reuse across requests."""
    global _model
    if _model is None:
        try:
            _model = models.Cellpose(gpu=False, model_type=cfg.CELLPOSE_MODEL)
        except AttributeError:
            _model = models.CellposeModel(gpu=False, model_type=cfg.CELLPOSE_MODEL)
    return _model


def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    img_adaptive = exposure.equalize_adapthist(gray, clip_limit=cfg.CLAHE_CLIP_LIMIT)
    img_adaptive = (img_adaptive * 255).astype(np.uint8)
    img_adaptive_rgb = cv2.cvtColor(img_adaptive, cv2.COLOR_GRAY2RGB)
    return img_adaptive_rgb, gray


def detect_background(img, masks):
    red = img[:, :, 0].astype(float)
    green = img[:, :, 1].astype(float)
    blue = img[:, :, 2].astype(float)
    background_mask = masks == 0
    if np.sum(background_mask) > 100:
        bg_r = np.median(red[background_mask])
        bg_g = np.median(green[background_mask])
        bg_b = np.median(blue[background_mask])
    else:
        bg_r = np.percentile(red, 90)
        bg_g = np.percentile(green, 90)
        bg_b = np.percentile(blue, 90)
    return np.array([bg_r, bg_g, bg_b])


def resize_if_large(img, max_dim=1024):
    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def segment_image(img_rgb, gray=None):
    """
    Runs Cellpose on a preprocessed RGB image.
    Returns (masks, valid_regions) where valid_regions is the list of
    skimage regionprops objects passing the area filter
    (MIN_CELL_AREA_PX .. MAX_CELL_AREA_PX).
    """
    from skimage import measure

    model = get_model()
    result = model.eval(
        img_rgb,
        diameter=cfg.DIAMETER_PX,
        flow_threshold=cfg.FLOW_THRESHOLD,
        cellprob_threshold=cfg.CELLPROB_THRESHOLD,
        channels=[0, 0],
    )
    masks = result[0] if isinstance(result, tuple) else result

    regions = measure.regionprops(masks, intensity_image=gray)
    valid_regions = [
        r for r in regions
        if cfg.MIN_CELL_AREA_PX <= r.area <= cfg.MAX_CELL_AREA_PX
    ]
    return masks, valid_regions
