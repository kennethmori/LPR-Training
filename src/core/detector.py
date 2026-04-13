from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class PlateDetector:
    def __init__(self, weights_path: Path, settings: dict[str, Any]) -> None:
        self.weights_path = weights_path
        self.settings = settings
        self.model = None
        self.mode = "unavailable"
        self.ready = False
        self._load()

    def _load(self) -> None:
        if not self.weights_path.exists():
            self.mode = "missing_weights"
            return

        try:
            from ultralytics import YOLO
        except Exception:
            self.mode = "ultralytics_not_installed"
            return

        try:
            self.model = YOLO(str(self.weights_path))
            self.mode = "yolo"
            self.ready = True
        except Exception:
            self.model = None
            self.mode = "load_failed"
            self.ready = False

    def detect(self, image: np.ndarray) -> list[dict[str, Any]]:
        if not self.ready or self.model is None:
            return []

        predictions = self.model.predict(
            source=image,
            conf=float(self.settings.get("confidence_threshold", 0.3)),
            iou=float(self.settings.get("iou_threshold", 0.5)),
            max_det=int(self.settings.get("max_detections", 5)),
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
