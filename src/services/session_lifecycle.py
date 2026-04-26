from __future__ import annotations

from typing import Any

from src.domain.models import RecognitionEvent, SessionDecision
from src.services.session_rules import normalized_plate_number, should_refine_open_session


def handle_entry_event(service: Any, event_row: RecognitionEvent) -> dict[str, Any]:
    near_open_session, near_open_session_distance = service._find_recent_ambiguous_open_session(event_row)
    if near_open_session is not None:
        return _handle_near_open_entry(service, event_row, near_open_session, near_open_session_distance)

    plate_number = normalized_plate_number(event_row.plate_number)
    open_session = service.session_repository.find_open_session(plate_number)
    if open_session and service.allow_only_one_open_session_per_plate:
        return service._log_ignored_event(
            event=event_row,
            event_action="ignored_duplicate",
            reason="open_session_already_exists",
            extra={"session_id": int(open_session["id"])},
        )

    event_id = service.event_repository.insert_recognition_event(event=event_row, event_action="session_opened")
    session_id = service.session_repository.create_vehicle_session(recognition_event_id=event_id, event=event_row)
    service.event_repository.update_recognition_event_links(
        recognition_event_id=event_id,
        created_session_id=session_id,
    )
    return SessionDecision(
        status="processed",
        event_action="session_opened",
        recognition_event_id=event_id,
        session_id=session_id,
    ).to_dict()


def handle_exit_event(service: Any, event_row: RecognitionEvent) -> dict[str, Any]:
    plate_number = normalized_plate_number(event_row.plate_number)
    open_session = service.session_repository.find_open_session(plate_number)
    close_note = ""
    if open_session is None:
        near_open_session, near_open_session_distance = service._find_recent_ambiguous_exit_session(event_row)
        if near_open_session is not None:
            near_session_plate = str(near_open_session.get("plate_number", "")).strip().upper()
            close_note = f"near_open_session:{near_session_plate}:distance_{near_open_session_distance}"
            open_session = near_open_session

    if open_session:
        return _close_open_session(service, event_row, open_session, close_note)

    return _log_unmatched_exit(service, event_row)


def _handle_near_open_entry(
    service: Any,
    event_row: RecognitionEvent,
    near_open_session: dict[str, Any],
    near_open_session_distance: int,
) -> dict[str, Any]:
    near_session_id = int(near_open_session["id"])
    near_session_plate = str(near_open_session.get("plate_number", "")).strip().upper()
    near_open_reason = f"near_open_session:{near_session_plate}:distance_{near_open_session_distance}"
    if should_refine_open_session(event_row, near_open_session):
        service.session_repository.update_open_session_entry_from_event(
            session_id=near_session_id,
            event=event_row,
            note=near_open_reason,
        )
        entry_event_id = near_open_session.get("entry_event_id")
        if entry_event_id is not None:
            service.event_repository.update_recognition_event_from_event(
                recognition_event_id=int(entry_event_id),
                event=event_row,
                note=near_open_reason,
            )
        return service._log_ignored_event(
            event=event_row,
            event_action="ignored_ambiguous_near_match",
            reason=f"{near_open_reason}:refined_open_session",
            extra={
                "session_id": near_session_id,
                "session_updated": True,
            },
            status="merged",
        )

    return service._log_ignored_event(
        event=event_row,
        event_action="ignored_ambiguous_near_match",
        reason=near_open_reason,
        extra={"session_id": near_session_id},
    )


def _close_open_session(
    service: Any,
    event_row: RecognitionEvent,
    open_session: dict[str, Any],
    close_note: str,
) -> dict[str, Any]:
    event_id = service.event_repository.insert_recognition_event(
        event=event_row,
        event_action="session_closed",
        note=close_note,
    )
    session_id = int(open_session["id"])
    service.session_repository.close_vehicle_session(
        session_id=session_id,
        recognition_event_id=event_id,
        event=event_row,
    )
    service.event_repository.update_recognition_event_links(
        recognition_event_id=event_id,
        closed_session_id=session_id,
    )
    return SessionDecision(
        status="processed",
        event_action="session_closed",
        recognition_event_id=event_id,
        session_id=session_id,
    ).to_dict()


def _log_unmatched_exit(service: Any, event_row: RecognitionEvent) -> dict[str, Any]:
    event_id = service.event_repository.insert_recognition_event(event=event_row, event_action="unmatched_exit")
    unmatched_exit_id = None
    if service.store_unmatched_exit_events:
        unmatched_exit_id = service.session_repository.insert_unmatched_exit(
            recognition_event_id=event_id,
            event=event_row,
            reason="no_open_session_for_plate",
        )
    decision = SessionDecision(
        status="processed",
        event_action="unmatched_exit",
        recognition_event_id=event_id,
        unmatched_exit_id=unmatched_exit_id,
    ).to_dict()
    decision.setdefault("unmatched_exit_id", unmatched_exit_id)
    return decision
