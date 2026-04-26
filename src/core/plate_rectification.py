from __future__ import annotations

import numpy as np

from src.core.plate_rectification_geometry import (
    as_grayscale,
    collect_rectification_candidates,
    warp_plate_quad,
)
from src.core.plate_rectification_scoring import rectified_crop_score


def rectify_plate_for_ocr(image: np.ndarray, settings: dict[str, object] | None = None) -> np.ndarray:
    if image is None or image.size == 0:
        return image

    options = settings or {}
    if not bool(options.get("rectify_plate_enabled", False)):
        return image

    image_height, image_width = image.shape[:2]
    image_area = float(max(image_height * image_width, 1))
    min_area_ratio = max(float(options.get("rectify_min_area_ratio", 0.08) or 0.08), 0.01)
    min_aspect_ratio = max(float(options.get("rectify_min_aspect_ratio", 1.8) or 1.8), 1.0)
    max_aspect_ratio = max(float(options.get("rectify_max_aspect_ratio", 8.0) or 8.0), min_aspect_ratio)
    min_side_px = max(int(options.get("rectify_min_side_px", 24) or 24), 8)
    grayscale = as_grayscale(image)
    candidates = collect_rectification_candidates(
        grayscale,
        image_area=image_area,
        min_area_ratio=min_area_ratio,
        min_aspect_ratio=min_aspect_ratio,
        max_aspect_ratio=max_aspect_ratio,
        min_side_px=min_side_px,
    )
    if not candidates:
        return image

    best_image = image
    best_score = rectified_crop_score(image, options)
    score_margin = max(float(options.get("rectify_score_margin", 10.0) or 10.0), 0.0)
    score_ratio = max(float(options.get("rectify_score_improvement_ratio", 0.06) or 0.06), 0.0)
    max_candidates = max(int(options.get("rectify_max_candidates", 8) or 8), 1)

    for _, quad in candidates[:max_candidates]:
        warped = warp_plate_quad(image, quad)
        if warped is None or warped.size == 0:
            continue

        warped_score = rectified_crop_score(warped, options)
        improved = (warped_score - best_score) > score_margin or warped_score > (best_score * (1.0 + score_ratio))
        if improved:
            best_image = warped
            best_score = warped_score

    return best_image
