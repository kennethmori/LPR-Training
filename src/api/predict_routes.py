from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src.api.dashboard_support import record_performance_snapshot
from src.api.schemas import PipelinePayload, VideoUploadPayload
from src.api.settings_support import attach_vehicle_lookup_to_payload
from src.services.upload_processing_service import (
    UploadProcessingError,
    UploadSizeLimitExceededError,
    as_normalized_set,
    process_image_upload_sync,
    process_video_upload_sync,
    resolve_max_upload_bytes,
    safe_upload_name,
    upload_settings_for_state,
    validate_upload_type,
)


def _cache_upload_payload(request: Request, payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    request.app.state.latest_payload = payload
    request.app.state.latest_payloads["upload"] = payload
    record_performance_snapshot(request, source=source, force=True)
    return payload


def register_predict_routes(router: APIRouter) -> None:
    @router.post("/predict/image", response_model=PipelinePayload)
    def predict_image(request: Request, file: UploadFile = File(...)):
        filename = safe_upload_name(file.filename, "uploaded_image.jpg")
        request_upload_settings = upload_settings_for_state(request.app.state)
        allowed_image_extensions = as_normalized_set(
            request_upload_settings.get("allowed_image_extensions"),
            (".jpg", ".jpeg", ".png", ".bmp", ".webp"),
        )
        allowed_image_mime_types = as_normalized_set(
            request_upload_settings.get("allowed_image_mime_types"),
            ("image/jpeg", "image/png", "image/bmp", "image/webp"),
        )
        max_image_bytes = resolve_max_upload_bytes(
            request_upload_settings,
            key="max_image_bytes",
            fallback=10 * 1024 * 1024,
        )
        try:
            try:
                validate_upload_type(
                    content_type=file.content_type,
                    filename=filename,
                    allowed_extensions=allowed_image_extensions,
                    allowed_mime_types=allowed_image_mime_types,
                    file_kind="image",
                )
                payload = process_image_upload_sync(
                    request.app.state,
                    file.file,
                    filename=filename,
                    max_image_bytes=max_image_bytes,
                )
            except UploadProcessingError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        finally:
            file.file.close()

        payload = attach_vehicle_lookup_to_payload(request, payload)
        return _cache_upload_payload(request, payload, source="predict_image")

    @router.post("/predict/video", response_model=VideoUploadPayload)
    def predict_video(request: Request, file: UploadFile = File(...)):
        filename = safe_upload_name(file.filename, "uploaded_video.mp4")
        request_upload_settings = upload_settings_for_state(request.app.state)
        allowed_video_extensions = as_normalized_set(
            request_upload_settings.get("allowed_video_extensions"),
            (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"),
        )
        allowed_video_mime_types = as_normalized_set(
            request_upload_settings.get("allowed_video_mime_types"),
            (
                "video/mp4",
                "video/x-msvideo",
                "video/quicktime",
                "video/x-matroska",
                "video/webm",
            ),
        )
        max_video_bytes = resolve_max_upload_bytes(
            request_upload_settings,
            key="max_video_bytes",
            fallback=100 * 1024 * 1024,
        )

        try:
            try:
                validate_upload_type(
                    content_type=file.content_type,
                    filename=filename,
                    allowed_extensions=allowed_video_extensions,
                    allowed_mime_types=allowed_video_mime_types,
                    file_kind="video",
                )
                response_payload, status_code = process_video_upload_sync(
                    request.app.state,
                    file.file,
                    filename,
                    max_video_bytes,
                )
            except UploadSizeLimitExceededError as exc:
                raise HTTPException(status_code=413, detail=f"Video upload exceeds {exc.limit_bytes} bytes.") from exc
            except UploadProcessingError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

            if status_code == 200:
                response_payload = attach_vehicle_lookup_to_payload(request, response_payload)
                return _cache_upload_payload(request, response_payload, source="predict_video")
            return JSONResponse(status_code=status_code, content=response_payload)
        finally:
            file.file.close()
