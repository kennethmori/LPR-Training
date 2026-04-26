from __future__ import annotations

from typing import Any, Callable

from src.services.camera_support import attach_camera_images, should_emit_payload


def apply_camera_payload(
    *,
    pipeline: Any,
    settings: dict[str, Any],
    payload: dict[str, Any],
    annotated_frame: Any,
    crop_image: Any,
    processed_payload_count: int,
    on_payload: Callable[[dict[str, Any]], None] | None,
    set_latest_payload: Callable[[dict[str, Any]], None],
    set_latest_detected_payload: Callable[[dict[str, Any]], None],
) -> None:
    attach_camera_images(
        pipeline=pipeline,
        settings=settings,
        payload=payload,
        annotated_frame=annotated_frame,
        crop_image=crop_image,
    )
    set_latest_payload(payload)
    if payload.get("plate_detected"):
        set_latest_detected_payload(dict(payload))
    if on_payload is not None and should_emit_payload(
        settings,
        payload=payload,
        processed_payload_count=processed_payload_count,
    ):
        on_payload(payload)
