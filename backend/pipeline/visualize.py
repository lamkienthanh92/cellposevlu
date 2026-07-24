"""
Builds the three overlay images the frontend shows when a person clicks
a result: the original image, the segmentation contours, and the Gram
classification contours (colored by vote outcome). Encoded as base64
PNG data-URLs so the API can return them as plain JSON fields.
"""
import base64
import io

import cv2
import numpy as np
from PIL import Image

COLOR_SEG = (0, 220, 200)
COLOR_GRAM_POS = (150, 100, 220)
COLOR_GRAM_NEG = (230, 110, 130)
COLOR_UNCLEAR = (140, 140, 140)

_GRAM_COLOR_MAP = {
    "gram_positive": COLOR_GRAM_POS,
    "gram_negative": COLOR_GRAM_NEG,
    "unclear": COLOR_UNCLEAR,
}


def encode_png_b64(img_rgb: np.ndarray) -> str:
    """RGB numpy array -> data-URL base64 PNG string."""
    pil_img = Image.fromarray(img_rgb.astype(np.uint8))
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def draw_contours(img_rgb, masks, valid_regions, labels_dict=None, color=COLOR_SEG):
    """
    Draws one contour per valid region on a copy of img_rgb.
    If labels_dict (region.label -> gram classification string) is
    given, each contour is colored by its Gram classification instead
    of the flat `color`.
    """
    overlay = img_rgb.copy()
    for region in valid_regions:
        cell_mask = (masks == region.label).astype(np.uint8)
        contours, _ = cv2.findContours(cell_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if labels_dict is not None:
            line_color = _GRAM_COLOR_MAP.get(labels_dict.get(region.label), COLOR_UNCLEAR)
        else:
            line_color = color
        cv2.drawContours(overlay, contours, -1, line_color, 1)
    return overlay


def build_result_images(img_rgb, masks, valid_regions, cell_labels):
    """
    Returns {"original": ..., "segmentation": ..., "gram": ...} where
    each value is a base64 PNG data-URL ready to drop into an <img src>.
    """
    seg_overlay = draw_contours(img_rgb, masks, valid_regions)
    gram_overlay = draw_contours(img_rgb, masks, valid_regions, labels_dict=cell_labels)
    return {
        "original": encode_png_b64(img_rgb),
        "segmentation": encode_png_b64(seg_overlay),
        "gram": encode_png_b64(gram_overlay),
    }
