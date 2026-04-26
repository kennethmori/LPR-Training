from __future__ import annotations

from typing import Any


class RuntimePayloadService:
    def __init__(self, services: Any) -> None:
        self.services = services

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        recognition_event = payload.get("recognition_event")
        if not recognition_event:
            payload["vehicle_lookup"] = None
            return None

        lookup_result = self.services.vehicle_registry_service.annotate_recognition_event(recognition_event)
        normalized_event = lookup_result["event"]
        payload["recognition_event"] = normalized_event
        payload["vehicle_lookup"] = lookup_result["vehicle_lookup"]

        session_result = self.services.session_service.process_recognition_event(normalized_event)
        append_session_result_log(
            logging_service=self.services.logging_service,
            recognition_event=normalized_event,
            session_result=session_result,
        )
        return session_result


def append_session_result_log(
    *,
    logging_service: Any,
    recognition_event: dict[str, Any] | None,
    session_result: dict[str, Any] | None,
) -> None:
    if not recognition_event or not session_result:
        return

    event_action = str(session_result.get("event_action", "") or "").strip().lower()
    if not event_action:
        return

    note_parts: list[str] = []
    status = str(session_result.get("status", "") or "").strip().lower()
    if status:
        note_parts.append(f"session_status={status}")

    reason = str(session_result.get("reason", "") or "").strip()
    if reason:
        note_parts.append(reason)

    recognition_event_id = session_result.get("recognition_event_id")
    if recognition_event_id is not None:
        note_parts.append(f"recognition_event_id={recognition_event_id}")

    session_id = session_result.get("session_id")
    if session_id is not None:
        note_parts.append(f"session_id={session_id}")

    unmatched_exit_id = session_result.get("unmatched_exit_id")
    if unmatched_exit_id is not None:
        note_parts.append(f"unmatched_exit_id={unmatched_exit_id}")

    logging_service.append(
        {
            "timestamp": recognition_event.get("timestamp"),
            "source_type": recognition_event.get("source_type", "camera"),
            "camera_role": recognition_event.get("camera_role", "unknown"),
            "source_name": recognition_event.get("source_name", ""),
            "plate_detected": True,
            "plate_number": recognition_event.get("plate_number", ""),
            "raw_text": recognition_event.get("raw_text", ""),
            "cleaned_text": recognition_event.get("cleaned_text", ""),
            "stable_text": recognition_event.get("stable_text", ""),
            "detector_confidence": float(recognition_event.get("detector_confidence", 0.0) or 0.0),
            "ocr_confidence": float(recognition_event.get("ocr_confidence", 0.0) or 0.0),
            "ocr_engine": recognition_event.get("ocr_engine", ""),
            "crop_path": recognition_event.get("crop_path"),
            "annotated_frame_path": recognition_event.get("annotated_frame_path"),
            "is_stable": bool(recognition_event.get("is_stable", False)),
            "event_action": event_action,
            "note": " | ".join(note_parts),
        }
    )
