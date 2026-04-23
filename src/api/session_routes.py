from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.api.schemas import RecognitionEventPayload, UnmatchedExitEventPayload, VehicleSessionPayload


def register_session_routes(router: APIRouter) -> None:
    @router.get("/sessions/active", response_model=list[VehicleSessionPayload])
    def active_sessions(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_active_sessions(limit=limit)

    @router.get("/sessions/history", response_model=list[VehicleSessionPayload])
    def session_history(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_session_history(limit=limit)

    @router.get("/sessions/{session_id}", response_model=VehicleSessionPayload)
    def one_session(request: Request, session_id: int):
        session = request.app.state.session_service.get_session(session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return session

    @router.get("/events/recent", response_model=list[RecognitionEventPayload])
    def recent_events(
        request: Request,
        limit: int = Query(default=100, ge=1, le=500),
        include_unmatched: bool = Query(default=False),
        include_logged_only: bool = Query(default=False),
        include_ignored: bool = Query(default=False),
    ):
        return request.app.state.session_service.get_recent_events(
            limit=limit,
            include_unmatched=include_unmatched,
            include_logged_only=include_logged_only,
            include_ignored=include_ignored,
        )

    @router.get("/events/unmatched-exit", response_model=list[UnmatchedExitEventPayload])
    def unmatched_exit_events(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_unmatched_exit_events(limit=limit)
