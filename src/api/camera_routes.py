from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from src.api.dashboard_support import (
    camera_start_message,
    get_camera_or_404,
    latest_for_role,
    latest_payload_or_idle,
    record_performance_snapshot,
)
from src.api.response_payloads import (
    camera_start_failed_payload,
    camera_started_payload,
    camera_stopped_payload,
)
from src.api.schemas import CameraControlPayload


def register_camera_routes(router: APIRouter) -> None:
    @router.post("/cameras/{role}/start", response_model=CameraControlPayload)
    def start_camera_by_role(request: Request, role: str):
        camera = get_camera_or_404(request, role)
        started = camera.start()
        if started:
            record_performance_snapshot(request, source=f"camera_start:{role}", force=True)
            return camera_started_payload(role)
        message, error_code = camera_start_message(camera, role)
        return camera_start_failed_payload(role=role, message=message, error_code=error_code)

    @router.post("/cameras/{role}/stop", response_model=CameraControlPayload)
    def stop_camera_by_role(request: Request, role: str):
        camera = get_camera_or_404(request, role)
        camera.stop()
        record_performance_snapshot(request, source=f"camera_stop:{role}", force=True)
        return camera_stopped_payload(role)

    @router.get("/cameras/{role}/stream")
    def stream_by_role(request: Request, role: str):
        camera = get_camera_or_404(request, role)
        return StreamingResponse(
            camera.stream_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/cameras/{role}/latest-result")
    def latest_result_by_role(request: Request, role: str):
        return latest_for_role(request, role)

    @router.post("/camera/start", response_model=CameraControlPayload)
    def start_camera_compat(request: Request):
        return start_camera_by_role(request, request.app.state.default_camera_role)

    @router.post("/camera/stop", response_model=CameraControlPayload)
    def stop_camera_compat(request: Request):
        return stop_camera_by_role(request, request.app.state.default_camera_role)

    @router.get("/stream")
    def stream_compat(request: Request):
        return stream_by_role(request, request.app.state.default_camera_role)

    @router.get("/latest-result")
    def latest_result_compat(request: Request):
        return latest_payload_or_idle(request)
