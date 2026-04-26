from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)


def load_ultralytics_detector(
    *,
    weights_path: Path,
    log_import_error: Callable[[], None],
) -> tuple[Any | None, str, bool]:
    if not weights_path.exists():
        return None, "missing_weights", False

    try:
        from ultralytics import YOLO
    except (ImportError, OSError):
        log_import_error()
        return None, "ultralytics_not_installed", False

    try:
        return YOLO(str(weights_path)), "yolo", True
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError):
        logger.exception("Failed to load Ultralytics detector weights from '%s'.", weights_path)
        return None, "load_failed", False


def detect_with_ultralytics(
    *,
    model: Any,
    settings: dict[str, Any],
    image: np.ndarray,
) -> list[dict[str, Any]]:
    input_size = int(settings.get("input_size", 640) or 640)
    device = str(settings.get("device", "cpu") or "cpu")
    predictions = model.predict(
        source=image,
        conf=float(settings.get("confidence_threshold", 0.3)),
        iou=float(settings.get("iou_threshold", 0.5)),
        max_det=int(settings.get("max_detections", 5)),
        imgsz=input_size,
        device=device,
        verbose=False,
    )
    if not predictions:
        return []

    result = predictions[0]
    if getattr(result, "boxes", None) is None:
        return []

    detections: list[dict[str, Any]] = []
    names = getattr(result, "names", {0: "plate_number"})
    for box in result.boxes:
        xyxy = box.xyxy[0].tolist()
        confidence = float(box.conf[0].item())
        class_index = int(box.cls[0].item())
        detections.append(
            {
                "bbox": {
                    "x1": int(xyxy[0]),
                    "y1": int(xyxy[1]),
                    "x2": int(xyxy[2]),
                    "y2": int(xyxy[3]),
                },
                "confidence": confidence,
                "label": str(names.get(class_index, "plate_number")),
            }
        )

    detections.sort(key=lambda item: item["confidence"], reverse=True)
    return detections
