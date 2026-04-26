from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.models import RecognitionEvent, utc_now_iso
from src.services.session_rules import normalized_plate_number


class ManualOverrideError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = int(status_code)
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class ManualOverrideResult:
    plate_number: str
    recognition_event: dict[str, Any]
    session_result: dict[str, Any]
    vehicle_lookup: dict[str, Any] | None


def _manual_override_role(action: str, fallback_role: str) -> str:
    normalized_action = str(action or "").strip().lower()
    if normalized_action == "open_session_manually":
        return "entry"
    if normalized_action == "close_session_manually":
        return "exit"
    fallback = str(fallback_role or "").strip().lower()
    return fallback if fallback in {"entry", "exit"} else "entry"


def _manual_override_note(payload: Any) -> str:
    action = str(payload.action or "confirm_predicted").strip().lower()
    reason = str(payload.reason or "").strip()
    parts = [f"manual_override:{action}"]
    if reason:
        parts.append(reason)
    return " | ".join(parts)


def _build_manual_override_event(payload: Any, plate_number: str, action: str) -> RecognitionEvent:
    camera_role = _manual_override_role(action, payload.camera_role)
    return RecognitionEvent(
        timestamp=utc_now_iso(),
        camera_role=camera_role,
        source_name=payload.source_name or "manual_override",
        source_type="manual_override",
        raw_text=payload.raw_text or plate_number,
        cleaned_text=payload.cleaned_text or plate_number,
        stable_text=payload.stable_text or plate_number,
        plate_number=plate_number,
        detector_confidence=float(payload.detector_confidence or 1.0),
        ocr_confidence=float(payload.ocr_confidence or 1.0),
        ocr_engine=payload.ocr_engine or "manual_override",
        crop_path=payload.crop_path,
        annotated_frame_path=payload.annotated_frame_path,
        is_stable=True,
        stable_occurrences=99,
    ).normalized()


def _annotated_event_payload(app_state: Any, event: RecognitionEvent) -> tuple[dict[str, Any], dict[str, Any] | None]:
    registry_service = getattr(app_state, "vehicle_registry_service", None)
    if registry_service is None:
        return event.to_dict(), None

    lookup_result = registry_service.annotate_recognition_event(event)
    return lookup_result["event"], lookup_result["vehicle_lookup"]


def _apply_log_only_action(
    *,
    storage_service: Any,
    event_payload: dict[str, Any],
    event_action: str,
    reason: str,
    note: str,
) -> dict[str, Any]:
    event_id = storage_service.insert_recognition_event(
        event_payload,
        event_action=event_action,
        note=note,
    )
    return {
        "status": "ignored" if event_action == "ignored_low_quality" else "logged",
        "event_action": event_action,
        "reason": reason,
        "recognition_event_id": event_id,
    }


def _apply_session_action(app_state: Any, event_payload: dict[str, Any], note: str) -> dict[str, Any]:
    session_service = getattr(app_state, "session_service", None)
    if session_service is None:
        raise ManualOverrideError(503, "Session service unavailable.")

    session_result = session_service.process_recognition_event(event_payload)
    event_id = session_result.get("recognition_event_id")
    if event_id:
        storage_service = app_state.storage_service
        storage_service.event_repository.update_recognition_event_links(
            recognition_event_id=int(event_id),
            created_session_id=session_result.get("session_id")
            if session_result.get("event_action") == "session_opened"
            else None,
            closed_session_id=session_result.get("session_id")
            if session_result.get("event_action") == "session_closed"
            else None,
        )
        storage_service.event_repository.update_recognition_event_from_event(
            recognition_event_id=int(event_id),
            event=event_payload,
            note=note,
        )
    return session_result


def apply_manual_override(app_state: Any, payload: Any) -> ManualOverrideResult:
    storage_service = app_state.storage_service
    if storage_service is None or not getattr(storage_service, "ready", False):
        raise ManualOverrideError(503, "Storage service unavailable.")

    plate_number = normalized_plate_number(payload.plate_number)
    if not plate_number:
        raise ManualOverrideError(400, "A corrected plate number is required.")

    action = str(payload.action or "confirm_predicted").strip().lower()
    event = _build_manual_override_event(payload, plate_number, action)
    event_payload, vehicle_lookup = _annotated_event_payload(app_state, event)
    note = _manual_override_note(payload)

    if action == "false_read":
        session_result = _apply_log_only_action(
            storage_service=storage_service,
            event_payload=event_payload,
            event_action="ignored_low_quality",
            reason="manual_override_false_read",
            note=note,
        )
    elif action == "visitor_check":
        session_result = _apply_log_only_action(
            storage_service=storage_service,
            event_payload=event_payload,
            event_action="logged_only",
            reason="manual_override_visitor_check",
            note=note,
        )
    else:
        session_result = _apply_session_action(app_state, event_payload, note)

    event_payload["plate_number"] = plate_number
    return ManualOverrideResult(
        plate_number=plate_number,
        recognition_event=event_payload,
        session_result=session_result,
        vehicle_lookup=vehicle_lookup,
    )
