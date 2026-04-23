from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import ModerationActionPayload


def register_moderation_routes(router: APIRouter) -> None:
    @router.delete("/moderation/events/{event_id}", response_model=ModerationActionPayload)
    def delete_recognition_event(request: Request, event_id: int):
        deleted = request.app.state.storage_service.delete_recognition_event(recognition_event_id=event_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Recognition event not found: {event_id}")
        return {
            "status": "deleted",
            "message": f"Recognition event {event_id} deleted.",
            "deleted_id": event_id,
            "entity_type": "recognition_event",
        }

    @router.delete("/moderation/sessions/{session_id}", response_model=ModerationActionPayload)
    def delete_vehicle_session(request: Request, session_id: int):
        deleted = request.app.state.storage_service.delete_vehicle_session(session_id=session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Vehicle session not found: {session_id}")
        return {
            "status": "deleted",
            "message": f"Vehicle session {session_id} deleted.",
            "deleted_id": session_id,
            "entity_type": "vehicle_session",
        }

    @router.delete("/moderation/unmatched-exit/{unmatched_exit_id}", response_model=ModerationActionPayload)
    def delete_unmatched_exit(request: Request, unmatched_exit_id: int):
        deleted = request.app.state.storage_service.delete_unmatched_exit(unmatched_exit_id=unmatched_exit_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Unmatched exit not found: {unmatched_exit_id}")
        return {
            "status": "deleted",
            "message": f"Unmatched exit {unmatched_exit_id} deleted.",
            "deleted_id": unmatched_exit_id,
            "entity_type": "unmatched_exit",
        }
