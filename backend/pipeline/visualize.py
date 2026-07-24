"""
Builds the single combined figure the frontend shows when a person
clicks a result: original, segmentation contours, and Gram
classification contours (colored by vote outcome), laid out side by
side with labels in one PNG -- the same 3-panel layout used by the
standalone batch scripts, just rendered with PIL instead of
matplotlib so it can run headless inside the API request.
"""
import base64
import io

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

COLOR_SEG = (0, 220, 200)
COLOR_GRAM_POS = (150, 100, 220)
COLOR_GRAM_NEG = (230, 110, 130)
COLOR_UNCLEAR = (140, 140, 140)

_GRAM_COLOR_MAP = {
    "gram_positive": COLOR_GRAM_POS,
    "gram_negative": COLOR_GRAM_NEG,
    "unclear": COLOR_UNCLEAR,
}

_PANEL_GAP = 12
_LABEL_HEIGHT = 28
_BACKGROUND = (245, 245, 245)
_LABEL_COLOR = (30, 30, 30)


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


def build_combined_figure(img_rgb, masks, valid_regions, cell_labels):
    """
    Renders Original | Segmentation | Gram Classification as one
    labeled, side-by-side PNG and returns it as a base64 data URL.
    """
    seg_overlay = draw_contours(img_rgb, masks, valid_regions)
    gram_overlay = draw_contours(img_rgb, masks, valid_regions, labels_dict=cell_labels)

    panels = [
        ("Original", img_rgb),
        ("Segmentation (Omnipose)", seg_overlay),
        ("Gram Classification", gram_overlay),
    ]

    h, w = img_rgb.shape[:2]
    canvas_w = w * len(panels) + _PANEL_GAP * (len(panels) - 1)
    canvas_h = h + _LABEL_HEIGHT

    canvas = Image.new("RGB", (canvas_w, canvas_h), _BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for i, (label, panel_img) in enumerate(panels):
        x = i * (w + _PANEL_GAP)
        canvas.paste(Image.fromarray(panel_img.astype(np.uint8)), (x, _LABEL_HEIGHT))
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        draw.text((x + max(0, (w - text_w) // 2), 6), label, fill=_LABEL_COLOR, font=font)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
