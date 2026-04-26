from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Request

from src.api.response_payloads import manual_override_applied_payload, moderation_deleted_payload
from src.api.schemas import (
    ManualOverrideRequestPayload,
    ManualOverrideResponsePayload,
    ModerationActionPayload,
)
from src.services.manual_override_service import (
    ManualOverrideError,
    apply_manual_override as apply_manual_override_action,
)


def _delete_or_404(*, delete_fn: Callable[[], bool], not_found_message: str) -> None:
    if not delete_fn():
        raise HTTPException(status_code=404, detail=not_found_message)


def register_moderation_routes(router: APIRouter) -> None:
    @router.post("/moderation/manual-override", response_model=ManualOverrideResponsePayload)
    def apply_manual_override(request: Request, payload: ManualOverrideRequestPayload):
        try:
            result = apply_manual_override_action(request.app.state, payload)
        except ManualOverrideError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

        return manual_override_applied_payload(
            plate_number=result.plate_number,
            recognition_event=result.recognition_event,
            session_result=result.session_result,
            vehicle_lookup=result.vehicle_lookup,
        )

    @router.delete("/moderation/events/{event_id}", response_model=ModerationActionPayload)
    def delete_recognition_event(request: Request, event_id: int):
        _delete_or_404(
            delete_fn=lambda: request.app.state.storage_service.delete_recognition_event(
                recognition_event_id=event_id
            ),
            not_found_message=f"Recognition event not found: {event_id}",
        )
        return moderation_deleted_payload(
            deleted_id=event_id,
            entity_type="recognition_event",
            label="Recognition event",
        )

    @router.delete("/moderation/sessions/{session_id}", response_model=ModerationActionPayload)
    def delete_vehicle_session(request: Request, session_id: int):
        _delete_or_404(
            delete_fn=lambda: request.app.state.storage_service.delete_vehicle_session(session_id=session_id),
            not_found_message=f"Vehicle session not found: {session_id}",
        )
        return moderation_deleted_payload(
            deleted_id=session_id,
            entity_type="vehicle_session",
            label="Vehicle session",
        )

    @router.delete("/moderation/unmatched-exit/{unmatched_exit_id}", response_model=ModerationActionPayload)
    def delete_unmatched_exit(request: Request, unmatched_exit_id: int):
        _delete_or_404(
            delete_fn=lambda: request.app.state.storage_service.delete_unmatched_exit(
                unmatched_exit_id=unmatched_exit_id
            ),
            not_found_message=f"Unmatched exit not found: {unmatched_exit_id}",
        )
        return moderation_deleted_payload(
            deleted_id=unmatched_exit_id,
            entity_type="unmatched_exit",
            label="Unmatched exit",
        )
