from __future__ import annotations

from typing import Any

import cv2

TRACKER_RUNTIME_EXCEPTIONS: tuple[type[BaseException], ...] = (
    cv2.error,
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
)
TRACKER_BOX_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TypeError,
    ValueError,
)


def tracker_factory(backend: str) -> Any | None:
    normalized = str(backend or "auto").strip().lower()
    legacy = getattr(cv2, "legacy", None)

    candidates: list[Any] = []
    if normalized in {"auto", "csrt"}:
        if legacy is not None and hasattr(legacy, "TrackerCSRT_create"):
            candidates.append(legacy.TrackerCSRT_create)
        if hasattr(cv2, "TrackerCSRT_create"):
            candidates.append(cv2.TrackerCSRT_create)
        if normalized == "csrt" and not candidates:
            return None
    if normalized in {"auto", "kcf"}:
        if legacy is not None and hasattr(legacy, "TrackerKCF_create"):
            candidates.append(legacy.TrackerKCF_create)
        if hasattr(cv2, "TrackerKCF_create"):
            candidates.append(cv2.TrackerKCF_create)
        if normalized == "kcf" and not candidates:
            return None
    if normalized in {"none", "disabled"}:
        return None

    for factory in candidates:
        try:
            return factory()
        except TRACKER_RUNTIME_EXCEPTIONS:
            continue
    return None


def bbox_to_tracker_box(bbox: dict[str, int]) -> tuple[float, float, float, float]:
    return (
        float(bbox["x1"]),
        float(bbox["y1"]),
        float(int(bbox["x2"]) - int(bbox["x1"])),
        float(int(bbox["y2"]) - int(bbox["y1"])),
    )


def tracker_box_to_bbox(box: Any, image_shape: tuple[int, ...]) -> dict[str, int] | None:
    try:
        x, y, width, height = box
    except TRACKER_BOX_EXCEPTIONS:
        return None

    image_height = max(int(image_shape[0]), 1)
    image_width = max(int(image_shape[1]), 1)
    left = max(min(int(round(x)), image_width - 1), 0)
    top = max(min(int(round(y)), image_height - 1), 0)
    box_width = max(int(round(width)), 1)
    box_height = max(int(round(height)), 1)
    right = max(min(left + box_width, image_width), left + 1)
    bottom = max(min(top + box_height, image_height), top + 1)
    return {
        "x1": left,
        "y1": top,
        "x2": right,
        "y2": bottom,
    }


def coerce_bbox(value: Any) -> dict[str, int]:
    bbox = dict(value or {})
    return {
        "x1": int(bbox["x1"]),
        "y1": int(bbox["y1"]),
        "x2": int(bbox["x2"]),
        "y2": int(bbox["y2"]),
    }
