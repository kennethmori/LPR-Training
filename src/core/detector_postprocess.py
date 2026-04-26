from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def label_for_class(settings: dict[str, Any], class_index: int) -> str:
    configured = settings.get("class_names")
    if isinstance(configured, list) and 0 <= class_index < len(configured):
        return str(configured[class_index])
    return "plate_number"


def scale_xywh_to_original(
    box: np.ndarray,
    scale: float,
    pad_left: int,
    pad_top: int,
    original_shape: tuple[int, ...],
) -> dict[str, int]:
    center_x, center_y, width, height = [float(value) for value in box.tolist()]
    x1 = center_x - (width / 2.0)
    y1 = center_y - (height / 2.0)
    x2 = center_x + (width / 2.0)
    y2 = center_y + (height / 2.0)
    return scale_xyxy_to_original(
        box=np.asarray([x1, y1, x2, y2], dtype=np.float32),
        scale=scale,
        pad_left=pad_left,
        pad_top=pad_top,
        original_shape=original_shape,
    )


def scale_xyxy_to_original(
    box: np.ndarray,
    scale: float,
    pad_left: int,
    pad_top: int,
    original_shape: tuple[int, ...],
) -> dict[str, int]:
    original_height = int(original_shape[0])
    original_width = int(original_shape[1])
    x1, y1, x2, y2 = [float(value) for value in box.tolist()]

    x1 = (x1 - pad_left) / max(scale, 1e-6)
    y1 = (y1 - pad_top) / max(scale, 1e-6)
    x2 = (x2 - pad_left) / max(scale, 1e-6)
    y2 = (y2 - pad_top) / max(scale, 1e-6)

    x1 = int(np.clip(round(x1), 0, max(original_width - 1, 0)))
    y1 = int(np.clip(round(y1), 0, max(original_height - 1, 0)))
    x2 = int(np.clip(round(x2), x1 + 1, max(original_width, x1 + 1)))
    y2 = int(np.clip(round(y2), y1 + 1, max(original_height, y1 + 1)))

    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def postprocess_onnx_raw_output(
    *,
    predictions: np.ndarray,
    settings: dict[str, Any],
    scale: float,
    pad_left: int,
    pad_top: int,
    original_shape: tuple[int, ...],
) -> list[dict[str, Any]]:
    if predictions.shape[1] <= 4:
        return []

    boxes_xywh = predictions[:, :4]
    class_scores = predictions[:, 4:]
    if class_scores.size == 0:
        return []

    class_indices = class_scores.argmax(axis=1)
    confidences = class_scores.max(axis=1)
    confidence_threshold = float(settings.get("confidence_threshold", 0.3))
    candidate_indices = np.where(confidences >= confidence_threshold)[0]
    if candidate_indices.size == 0:
        return []

    boxes_for_nms: list[list[int]] = []
    selected_scores: list[float] = []
    candidate_rows: list[tuple[int, dict[str, int], float]] = []

    for index in candidate_indices:
        bbox = scale_xywh_to_original(
            box=boxes_xywh[index],
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=original_shape,
        )
        width = max(bbox["x2"] - bbox["x1"], 1)
        height = max(bbox["y2"] - bbox["y1"], 1)
        boxes_for_nms.append([bbox["x1"], bbox["y1"], width, height])
        selected_scores.append(float(confidences[index]))
        candidate_rows.append((int(class_indices[index]), bbox, float(confidences[index])))

    return _detections_after_nms(
        settings=settings,
        boxes_for_nms=boxes_for_nms,
        selected_scores=selected_scores,
        candidate_rows=candidate_rows,
    )


def postprocess_onnx_nms_output(
    *,
    predictions: np.ndarray,
    settings: dict[str, Any],
    scale: float,
    pad_left: int,
    pad_top: int,
    original_shape: tuple[int, ...],
) -> list[dict[str, Any]]:
    confidence_threshold = float(settings.get("confidence_threshold", 0.3))
    boxes_for_nms: list[list[int]] = []
    selected_scores: list[float] = []
    candidate_rows: list[tuple[int, dict[str, int], float]] = []

    for row in predictions:
        if row.shape[0] < 6:
            continue
        confidence = float(row[4])
        if confidence < confidence_threshold:
            continue

        class_index = int(row[5]) if row.shape[0] > 5 else 0
        bbox = scale_xyxy_to_original(
            box=row[:4],
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=original_shape,
        )
        width = max(bbox["x2"] - bbox["x1"], 1)
        height = max(bbox["y2"] - bbox["y1"], 1)
        boxes_for_nms.append([bbox["x1"], bbox["y1"], width, height])
        selected_scores.append(confidence)
        candidate_rows.append((class_index, bbox, confidence))

    if not candidate_rows:
        return []

    return _detections_after_nms(
        settings=settings,
        boxes_for_nms=boxes_for_nms,
        selected_scores=selected_scores,
        candidate_rows=candidate_rows,
    )


def _detections_after_nms(
    *,
    settings: dict[str, Any],
    boxes_for_nms: list[list[int]],
    selected_scores: list[float],
    candidate_rows: list[tuple[int, dict[str, int], float]],
) -> list[dict[str, Any]]:
    confidence_threshold = float(settings.get("confidence_threshold", 0.3))
    kept_indices = cv2.dnn.NMSBoxes(
        bboxes=boxes_for_nms,
        scores=selected_scores,
        score_threshold=confidence_threshold,
        nms_threshold=float(settings.get("iou_threshold", 0.5)),
    )
    if len(kept_indices) == 0:
        return []

    detections: list[dict[str, Any]] = []
    for kept_index in np.array(kept_indices).reshape(-1):
        class_index, bbox, confidence = candidate_rows[int(kept_index)]
        detections.append(
            {
                "bbox": bbox,
                "confidence": confidence,
                "label": label_for_class(settings, class_index),
            }
        )
    return detections
