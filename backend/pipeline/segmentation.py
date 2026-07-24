"""
Omnipose segmentation (bact_phase_affinity, fallback bact_phase_omni)
+ background estimation.

Replaces the earlier Cellpose 2.0 (cyto2) backend, which was found to
miss most rod-shaped/elongated bacteria on real Gram-stain images --
its flow-to-centroid approach only reliably handles roughly round
cells. Omnipose's distance-transform / medial-axis approach handles
both round and elongated cells in one model. The 5-vote Gram
classifier itself is unaffected by this change: it only reads the
average color inside each segmented cell, regardless of which model
produced the mask.
"""
import sys
import types

import cv2
import numpy as np
from skimage import exposure

from . import config as cfg

# --- Known dependency breakage in the current omnipose/cellpose_omni
# --- release chain on PyPI -- patched directly here rather than
# --- chasing exact compatible version pins across a fast-moving dep
# --- tree. Both patches are no-ops if a future release fixes them.
#
# 1) cellpose_omni unconditionally imports aicsimageio (a bio-format
#    reader this app never uses -- images are loaded via PIL). Its
#    tiff_reader.py references TIFF.RESUNIT, which newer `tifffile`
#    releases removed/restructured, crashing the import with:
#      AttributeError: '_TIFF' object has no attribute 'RESUNIT'
_tiff_reader_stub = types.ModuleType("aicsimageio.readers.tiff_reader")
_tiff_reader_stub.TiffReader = object
sys.modules.setdefault("aicsimageio.readers.tiff_reader", _tiff_reader_stub)

import ncolor  # noqa: E402  (must come after the stub above)

# 2) omnipose.misc does `from ncolor import unique_nonzero`, but some
#    resolved `ncolor` releases renamed/removed it:
#      ImportError: cannot import name 'unique_nonzero' from 'ncolor'
if not hasattr(ncolor, "unique_nonzero"):
    def _unique_nonzero(arr):
        u = np.unique(arr)
        return u[u != 0]
    ncolor.unique_nonzero = _unique_nonzero

from cellpose_omni import models  # noqa: E402
from omnipose.utils import normalize99  # noqa: E402

_model = None
_model_type = cfg.OMNIPOSE_MODEL_TYPE


def get_model():
    """Load the Omnipose model once and reuse across requests."""
    global _model, _model_type
    if _model is None:
        try:
            _model = models.CellposeModel(gpu=False, model_type=_model_type)
        except Exception:
            _model_type = cfg.OMNIPOSE_FALLBACK_MODEL_TYPE
            _model = models.CellposeModel(gpu=False, model_type=_model_type)
    return _model


def preprocess_image(img):
    """
    Returns (img_adaptive_rgb, gray). `gray` is the raw (pre-CLAHE)
    grayscale image -- this is what gets fed to Omnipose (via
    normalize99) and to the SV2 texture/edge feature extractors,
    matching the reference pipeline. `img_adaptive_rgb` is kept for
    parity with the original interface; nothing currently reads it.
    """
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


def segment_image(gray):
    """
    Runs Omnipose on a raw grayscale image (normalized via Omnipose's
    own normalize99). Returns (masks, valid_regions) where
    valid_regions is the list of skimage regionprops objects passing
    the area filter (MIN_CELL_AREA_PX .. MAX_CELL_AREA_PX).
    """
    from skimage import measure

    model = get_model()
    img_gray_norm = normalize99(gray.astype(float))
    masks_list, _flows, _styles = model.eval([img_gray_norm], **cfg.OMNI_PARAMS)
    masks = masks_list[0]

    regions = measure.regionprops(masks)
    valid_regions = [
        r for r in regions
        if cfg.MIN_CELL_AREA_PX <= r.area <= cfg.MAX_CELL_AREA_PX
    ]
    return masks, valid_regions
