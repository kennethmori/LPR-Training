from __future__ import annotations

from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src.api.dashboard_support import record_performance_snapshot
from src.api.schemas import PipelinePayload, VideoUploadPayload
from src.api.settings_support import attach_vehicle_lookup_to_payload
from src.api.upload_support import (
    UploadSizeLimitExceededError,
    as_normalized_set,
    process_video_upload_sync,
    resolve_max_upload_bytes,
    safe_upload_name,
    upload_settings,
    validate_upload_type,
)


def register_predict_routes(router: APIRouter) -> None:
    @router.post("/predict/image", response_model=PipelinePayload)
    def predict_image(request: Request, file: UploadFile = File(...)):
        filename = safe_upload_name(file.filename, "uploaded_image.jpg")
        request_upload_settings = upload_settings(request)
        allowed_image_extensions = as_normalized_set(
            request_upload_settings.get("allowed_image_extensions"),
            (".jpg", ".jpeg", ".png", ".bmp", ".webp"),
        )
        allowed_image_mime_types = as_normalized_set(
            request_upload_settings.get("allowed_image_mime_types"),
            ("image/jpeg", "image/png", "image/bmp", "image/webp"),
        )
        validate_upload_type(
            upload=file,
            filename=filename,
            allowed_extensions=allowed_image_extensions,
            allowed_mime_types=allowed_image_mime_types,
            file_kind="image",
        )

        max_image_bytes = resolve_max_upload_bytes(
            request_upload_settings,
            key="max_image_bytes",
            fallback=10 * 1024 * 1024,
        )
        try:
            file.file.seek(0)
            content = file.file.read(max_image_bytes + 1)
        finally:
            file.file.close()

        if not content:
            raise HTTPException(status_code=400, detail="Empty image upload.")
        if len(content) > max_image_bytes:
            raise HTTPException(status_code=413, detail=f"Image upload exceeds {max_image_bytes} bytes.")

        image_array = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image upload.")

        pipeline = request.app.state.pipeline
        stream_key = f"upload:image:{uuid4().hex}"
        try:
            payload, annotated, crop = pipeline.process_frame(
                image,
                source_type="upload",
                camera_role="upload",
                source_name=filename,
                stream_key=stream_key,
            )
        finally:
            pipeline.clear_stream_state(stream_key)
        payload = attach_vehicle_lookup_to_payload(request, payload)
        payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
        payload["crop_image_base64"] = pipeline.encode_image_base64(crop)
        request.app.state.latest_payload = payload
        request.app.state.latest_payloads["upload"] = payload
        record_performance_snapshot(request, source="predict_image", force=True)
        return payload

    @router.post("/predict/video", response_model=VideoUploadPayload)
    def predict_video(request: Request, file: UploadFile = File(...)):
        filename = safe_upload_name(file.filename, "uploaded_video.mp4")
        request_upload_settings = upload_settings(request)
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
        validate_upload_type(
            upload=file,
            filename=filename,
            allowed_extensions=allowed_video_extensions,
            allowed_mime_types=allowed_video_mime_types,
            file_kind="video",
        )
        max_video_bytes = resolve_max_upload_bytes(
            request_upload_settings,
            key="max_video_bytes",
            fallback=100 * 1024 * 1024,
        )

        try:
            try:
                response_payload, status_code = process_video_upload_sync(
                    request.app.state,
                    file.file,
                    filename,
                    max_video_bytes,
                )
            except UploadSizeLimitExceededError as exc:
                raise HTTPException(status_code=413, detail=f"Video upload exceeds {exc.limit_bytes} bytes.") from exc

            if status_code == 200:
                response_payload = attach_vehicle_lookup_to_payload(request, response_payload)
                request.app.state.latest_payload = response_payload
                request.app.state.latest_payloads["upload"] = response_payload
                record_performance_snapshot(request, source="predict_video", force=True)
                return response_payload
            return JSONResponse(status_code=status_code, content=response_payload)
        finally:
            file.file.close()
