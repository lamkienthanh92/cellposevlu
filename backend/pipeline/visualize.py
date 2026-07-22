"""
Generates the 3 images the frontend shows per analysed image:
  1. original         — the input image, resized, as-is
  2. segmented         — cell boundaries outlined on the original
  3. gram_classified    — cell boundaries colored by Gram classification
"""
import base64

import cv2
import numpy as np

# BGR colors (cv2 draws in BGR)
COLOR_SEG = (0, 255, 200)        # cyan-ish outline for plain segmentation
COLOR_GRAM_POS = (200, 100, 100)   # violet-ish, ~ [100,100,180] in RGB reversed to BGR-ish accent
COLOR_GRAM_NEG = (140, 130, 210)   # pink-ish, ~ [200,130,140] in RGB reversed
COLOR_UNCLEAR = (120, 120, 120)    # gray


def _encode_png_b64(img_rgb):
    ok, buf = cv2.imencode(".png", cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


def render_original(img_rgb):
    return _encode_png_b64(img_rgb)


def render_segmentation_overlay(img_rgb, masks, valid_regions):
    overlay = img_rgb.copy()
    for region in valid_regions:
        cell_mask = (masks == region.label).astype(np.uint8)
        contours, _ = cv2.findContours(cell_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, COLOR_SEG, 1)
    return _encode_png_b64(overlay)


def render_gram_overlay(img_rgb, masks, valid_regions, cell_labels):
    """
    cell_labels: dict {region.label: 'gram_positive'|'gram_negative'|'unclear'}
    """
    overlay = img_rgb.copy()
    color_map = {
        "gram_positive": COLOR_GRAM_POS,
        "gram_negative": COLOR_GRAM_NEG,
        "unclear": COLOR_UNCLEAR,
    }
    for region in valid_regions:
        cell_mask = (masks == region.label).astype(np.uint8)
        contours, _ = cv2.findContours(cell_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        color = color_map.get(cell_labels.get(region.label), COLOR_UNCLEAR)
        cv2.drawContours(overlay, contours, -1, color, 2)
    return _encode_png_b64(overlay)
