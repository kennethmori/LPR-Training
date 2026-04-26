from __future__ import annotations

import cv2
import numpy as np

from src.core.plate_rectification_geometry import as_grayscale


def _component_line_score(mask: np.ndarray) -> float:
    height, width = mask.shape[:2]
    image_area = float(max(height * width, 1))
    labels_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

    components: list[tuple[float, float, float]] = []
    for index in range(1, labels_count):
        _x, _y, component_width, component_height, area = stats[index]
        if area < max(image_area * 0.001, 4.0):
            continue
        if area > image_area * 0.2:
            continue
        if component_width < 2 or component_height < max(int(round(height * 0.12)), 4):
            continue
        if component_height >= height:
            continue
        if (component_width / max(component_height, 1)) > 4.5:
            continue

        center_x = float(centroids[index][0])
        center_y = float(centroids[index][1])
        components.append((center_x, center_y, float(area)))

    if len(components) < 2:
        return 0.0

    x_centers = np.asarray([row[0] for row in components], dtype=np.float32)
    y_centers = np.asarray([row[1] for row in components], dtype=np.float32)
    occupied_area = float(sum(row[2] for row in components))

    horizontal_span = (float(np.max(x_centers)) - float(np.min(x_centers))) / max(float(width), 1.0)
    vertical_spread = float(np.std(y_centers)) / max(float(height), 1.0)
    density = occupied_area / image_area

    count_bonus = min(len(components), 8) / 8.0
    alignment_bonus = max(0.0, 0.18 - vertical_spread) / 0.18
    span_bonus = max(0.0, min((horizontal_span - 0.25) / 0.55, 1.0))
    density_bonus = max(0.0, 1.0 - min(abs(density - 0.16) / 0.16, 1.0))
    return (count_bonus + alignment_bonus + span_bonus + density_bonus) / 4.0


def _character_band_score(gray: np.ndarray) -> float:
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))

    scores: list[float] = []
    for threshold_mode in (
        cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
        cv2.THRESH_BINARY | cv2.THRESH_OTSU,
    ):
        _, mask = cv2.threshold(blurred, 0, 255, threshold_mode)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel, iterations=1)
        scores.append(_component_line_score(mask))
    return max(scores, default=0.0)


def rectified_crop_score(image: np.ndarray, settings: dict[str, object]) -> float:
    gray = as_grayscale(image)
    height, width = gray.shape[:2]
    if width <= 1 or height <= 1:
        return float("-inf")

    aspect_ratio = float(width) / max(float(height), 1.0)
    min_aspect_ratio = max(float(settings.get("rectify_min_aspect_ratio", 1.8) or 1.8), 1.0)
    max_aspect_ratio = max(float(settings.get("rectify_max_aspect_ratio", 8.0) or 8.0), min_aspect_ratio)

    if aspect_ratio < 1.0:
        aspect_bonus = aspect_ratio * 0.35
    elif aspect_ratio > max_aspect_ratio * 1.5:
        aspect_bonus = max_aspect_ratio * 0.75
    else:
        aspect_bonus = min(max(aspect_ratio, min_aspect_ratio), max_aspect_ratio)

    contrast = float(np.std(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_32F).var())
    band_score = _character_band_score(gray)
    edge_density = float(np.count_nonzero(cv2.Canny(gray, 50, 150))) / float(max(gray.size, 1))

    return (
        (aspect_bonus * 40.0)
        + (min(contrast, 64.0) * 2.0)
        + (min(sharpness, 4000.0) * 0.02)
        + (band_score * 120.0)
        + (min(edge_density, 0.35) * 40.0)
    )
