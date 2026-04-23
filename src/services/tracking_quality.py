from __future__ import annotations

import cv2
import numpy as np


def compute_sharpness(image: np.ndarray | None) -> float:
    if image is None or image.size == 0:
        return 0.0
    try:
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    except cv2.error:
        return 0.0
    return float(cv2.Laplacian(grayscale, cv2.CV_64F).var())


def score_crop(width: int, height: int, sharpness: float, detector_confidence: float) -> float:
    area_score = max(width, 0) * max(height, 0)
    return area_score + (sharpness * 10.0) + (float(detector_confidence) * 1000.0)
