from __future__ import annotations

import cv2
import numpy as np


def expand_bbox(bbox: dict[str, int], image_shape: tuple[int, ...], padding_ratio: float) -> dict[str, int]:
    image_height, image_width = image_shape[:2]
    width = bbox["x2"] - bbox["x1"]
    height = bbox["y2"] - bbox["y1"]

    pad_x = int(width * padding_ratio)
    pad_y = int(height * padding_ratio)

    return {
        "x1": max(0, bbox["x1"] - pad_x),
        "y1": max(0, bbox["y1"] - pad_y),
        "x2": min(image_width, bbox["x2"] + pad_x),
        "y2": min(image_height, bbox["y2"] + pad_y),
    }


def crop_plate(image: np.ndarray, bbox: dict[str, int], padding_ratio: float) -> tuple[np.ndarray, dict[str, int]]:
    padded_bbox = expand_bbox(bbox, image.shape, padding_ratio)
    crop = image[padded_bbox["y1"]:padded_bbox["y2"], padded_bbox["x1"]:padded_bbox["x2"]]
    return crop, padded_bbox


def resize_for_ocr(image: np.ndarray, target_width: int) -> np.ndarray:
    height, width = image.shape[:2]
    if width == 0 or target_width <= 0 or width >= target_width:
        return image
    scale = target_width / width
    target_height = int(height * scale)
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_CUBIC)


def annotate_detection(
    image: np.ndarray,
    bbox: dict[str, int],
    label: str,
    score: float,
    text: str,
) -> np.ndarray:
    annotated = image.copy()
    cv2.rectangle(annotated, (bbox["x1"], bbox["y1"]), (bbox["x2"], bbox["y2"]), (15, 93, 184), 2)
    banner = f"{label} {score:.2f}"
    cv2.putText(annotated, banner, (bbox["x1"], max(20, bbox["y1"] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (15, 93, 184), 2)
    if text:
        cv2.putText(annotated, text, (bbox["x1"], min(annotated.shape[0] - 10, bbox["y2"] + 25)), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (26, 77, 46), 2)
    return annotated
