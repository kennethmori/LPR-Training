from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
import numpy as np
import yaml
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from src.api.schemas import (
    AppStatusPayload,
    CameraControlPayload,
    CameraSettingsPayload,
    CameraSettingsUpdatePayload,
    DetectorRuntimeSettingsPayload,
    DetectorRuntimeSettingsUpdatePayload,
    ModerationActionPayload,
    PerformanceSnapshotPayload,
    PerformanceSummaryPayload,
    PipelinePayload,
    RecognitionSettingsPayload,
    RecognitionSettingsUpdatePayload,
    RecognitionEventPayload,
    UnmatchedExitEventPayload,
    VideoUploadPayload,
    VehicleSessionPayload,
)
from src.core.detector import PlateDetector


class UploadSizeLimitExceededError(Exception):
    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = int(limit_bytes)
        super().__init__(f"upload_size_limit_exceeded:{self.limit_bytes}")


ARTIFACTS_ROOT = Path(__file__).resolve().parents[2] / "outputs"


def create_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()
    dashboard_cache_payload: dict[str, Any] | None = None
    dashboard_cache_updated_at = 0.0

    def _camera_start_message(camera: Any, role: str) -> tuple[str, str | None]:
        error_code = getattr(camera, "last_start_error", None)
        if error_code == "camera_source_missing":
            return (
                f"Camera '{role}' could not start because its phone camera source is not configured.",
                error_code,
            )
        if isinstance(error_code, str) and error_code.startswith("camera_open_failed:"):
            source = error_code.split(":", 1)[1]
            return (
                f"Camera '{role}' could not open source '{source}'. Make sure the phone stream is live and reachable.",
                error_code,
            )
        return (f"Unable to start camera '{role}'.", error_code)

    def _safe_upload_name(filename: str | None, fallback: str) -> str:
        candidate = (filename or "").strip()
        return candidate or fallback

    def _resolve_artifact_path(raw_path: str) -> Path:
        candidate = Path(str(raw_path or "").strip())
        if not candidate:
            raise HTTPException(status_code=400, detail="Missing artifact path.")
        resolved = candidate.expanduser().resolve()
        try:
            resolved.relative_to(ARTIFACTS_ROOT.resolve())
        except ValueError as exc:
            raise HTTPException(status_code=403, detail="Artifact path is outside outputs.") from exc
        if not resolved.is_file():
            raise HTTPException(status_code=404, detail="Artifact file not found.")
        return resolved

    def _string_or_empty(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_camera_source(value: Any) -> str | None:
        candidate = _string_or_empty(value)
        return candidate or None

    def _camera_settings_payload(request: Request) -> dict[str, Any]:
        settings = request.app.state.settings
        entry_camera = request.app.state.camera_services.get("entry")
        exit_camera = request.app.state.camera_services.get("exit")
        entry_source = _string_or_empty(entry_camera.settings.get("source") if entry_camera is not None else "")
        exit_source = _string_or_empty(exit_camera.settings.get("source") if exit_camera is not None else "")
        fallback_source = _string_or_empty((settings.get("camera") or {}).get("source"))
        return {
            "entry_source": entry_source,
            "exit_source": exit_source,
            "fallback_source": fallback_source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist_settings_file(request: Request) -> str | None:
        config_path = Path(request.app.state.config_path)
        try:
            with config_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    request.app.state.settings,
                    handle,
                    sort_keys=False,
                    allow_unicode=False,
                )
        except OSError as exc:
            return str(exc)
        return None

    def _apply_camera_settings(request: Request, role_sources: dict[str, str | None]) -> tuple[list[str], list[str]]:
        restarted_roles: list[str] = []
        failed_roles: list[str] = []
        camera_manager = request.app.state.camera_manager

        for role, source in role_sources.items():
            camera = request.app.state.camera_services.get(role)
            if camera is None:
                continue
            was_running = bool(camera.running)
            if was_running:
                camera.stop()
            camera.settings["source"] = source
            camera.last_start_error = None
            if was_running and source is not None:
                if camera.start():
                    restarted_roles.append(role)
                else:
                    failed_roles.append(role)

        request.app.state.camera_service = camera_manager.get(camera_manager.default_role)
        return restarted_roles, failed_roles

    def _recognition_settings_payload(request: Request) -> dict[str, Any]:
        session_settings = dict(request.app.state.settings.get("session", {}))
        ocr_settings = dict(request.app.state.settings.get("ocr", {}))
        return {
            "min_detector_confidence": float(session_settings.get("min_detector_confidence", 0.5) or 0.5),
            "min_ocr_confidence": float(session_settings.get("min_ocr_confidence", 0.9) or 0.9),
            "min_stable_occurrences": int(session_settings.get("min_stable_occurrences", 3) or 3),
            "ocr_cpu_threads": int(ocr_settings.get("cpu_threads", 8) or 8),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message": "",
        }

    def _resolved_detector_settings(request: Request) -> dict[str, Any]:
        detector_settings = dict(request.app.state.settings.get("detector", {}))
        onnx_weights_path = detector_settings.get("onnx_weights_path")
        if onnx_weights_path:
            base_dir = Path(request.app.state.base_dir)
            candidate = Path(str(onnx_weights_path))
            detector_settings["onnx_weights_path"] = str(
                candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()
            )
        return detector_settings

    def _build_detector(request: Request) -> PlateDetector:
        base_dir = Path(request.app.state.base_dir)
        return PlateDetector(
            weights_path=base_dir / request.app.state.settings["paths"]["detector_weights"],
            settings=_resolved_detector_settings(request),
        )

    def _detector_runtime_settings_payload(request: Request) -> dict[str, Any]:
        detector_settings = dict(request.app.state.settings.get("detector", {}))
        backend = str(detector_settings.get("backend", "ultralytics") or "ultralytics").strip().lower()
        if backend in {"onnx", "onnxruntime", "ort"}:
            backend = "onnxruntime"
        elif backend != "ultralytics":
            backend = "ultralytics"

        return {
            "backend": backend,
            "onnx_weights_path": str(detector_settings.get("onnx_weights_path", "models/detector/best.onnx") or ""),
            "detector_ready": bool(request.app.state.detector.ready),
            "detector_mode": str(request.app.state.detector.mode),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "message": "",
        }

    def _apply_detector_runtime_settings(
        request: Request,
        backend: str,
        onnx_weights_path: str,
    ) -> tuple[list[str], list[str]]:
        camera_manager = request.app.state.camera_manager
        running_roles = list(camera_manager.running_roles())
        for role in running_roles:
            camera_manager.stop(role)

        settings = request.app.state.settings
        settings.setdefault("detector", {})
        settings["detector"]["backend"] = backend
        settings["detector"]["onnx_weights_path"] = onnx_weights_path

        detector = _build_detector(request)
        request.app.state.detector = detector
        request.app.state.pipeline.detector = detector
        request.app.state.pipeline.settings["backend"] = backend
        request.app.state.pipeline.settings["onnx_weights_path"] = onnx_weights_path

        restarted_roles: list[str] = []
        failed_roles: list[str] = []
        for role in running_roles:
            if camera_manager.start(role):
                restarted_roles.append(role)
            else:
                failed_roles.append(role)
        return restarted_roles, failed_roles

    def _upload_settings(request: Request) -> dict:
        return dict(request.app.state.settings.get("uploads", {}))

    def _as_normalized_set(values: Any, defaults: tuple[str, ...]) -> set[str]:
        if not isinstance(values, list):
            return set(defaults)
        normalized = {
            str(item).strip().lower()
            for item in values
            if str(item).strip()
        }
        return normalized or set(defaults)

    def _resolve_max_upload_bytes(settings: dict[str, Any], key: str, fallback: int) -> int:
        configured = int(settings.get(key, fallback) or fallback)
        return max(configured, 1)

    def _validate_upload_type(
        *,
        upload: UploadFile,
        filename: str,
        allowed_extensions: set[str],
        allowed_mime_types: set[str],
        file_kind: str,
    ) -> None:
        extension = Path(filename).suffix.lower()
        content_type = str(upload.content_type or "").split(";")[0].strip().lower()

        extension_ok = extension in allowed_extensions
        content_type_ok = bool(content_type and content_type in allowed_mime_types)

        if content_type and not content_type_ok:
            raise HTTPException(status_code=415, detail=f"Unsupported {file_kind} content type: {content_type}")
        if not extension_ok and not content_type_ok:
            extension_label = extension or "<missing>"
            raise HTTPException(status_code=415, detail=f"Unsupported {file_kind} file type: {extension_label}")

    def _write_upload_stream(target_path: Path, binary_stream: Any, max_bytes: int) -> int:
        binary_stream.seek(0)
        total_written = 0
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as handle:
            while True:
                chunk = binary_stream.read(1024 * 1024)
                if not chunk:
                    break
                total_written += len(chunk)
                if total_written > max_bytes:
                    raise UploadSizeLimitExceededError(limit_bytes=max_bytes)
                handle.write(chunk)
        return total_written

    def _stage_video_upload(app_state: Any, binary_stream: Any, filename: str, max_video_bytes: int) -> Path:
        suffix = Path(filename).suffix or ".mp4"
        temp_token = uuid4().hex
        primary_path = app_state.video_upload_dir / f"{temp_token}{suffix}"
        fallback_path = Path(tempfile.gettempdir()) / f"plate_video_upload_{temp_token}{suffix}"

        last_error: OSError | None = None
        for candidate in (primary_path, fallback_path):
            try:
                _write_upload_stream(candidate, binary_stream, max_bytes=max_video_bytes)
                return candidate
            except UploadSizeLimitExceededError:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            except OSError as exc:
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    pass
                last_error = exc

        raise HTTPException(
            status_code=500,
            detail=f"Unable to stage uploaded video: {last_error}" if last_error else "Unable to stage uploaded video.",
        )

    def _payload_rank(payload: dict) -> tuple[int, int, int, float, float]:
        stable = payload.get("stable_result") or {}
        detection = payload.get("detection") or {}
        ocr = payload.get("ocr") or {}
        return (
            1 if stable.get("accepted") else 0,
            int(stable.get("occurrences") or 0),
            1 if payload.get("plate_detected") else 0,
            float(ocr.get("confidence") or 0.0),
            float(detection.get("confidence") or 0.0),
        )

    def _video_response_from_payload(
        representative_payload: dict | None,
        *,
        filename: str,
        status: str,
        message: str,
        total_frames: int,
        fps: float,
        processed_frames: int,
        processed_every_n_frames: int,
        detected_frames: int,
        stable_frames: int,
        recognized_plates: list[str],
        representative_frame_index: int | None,
        representative_timestamp_seconds: float | None,
    ) -> dict:
        payload = dict(representative_payload or {})
        payload["source_type"] = "video"
        payload["camera_role"] = "upload"
        payload["source_name"] = filename
        payload["status"] = status
        payload["message"] = message
        payload["video_summary"] = {
            "total_frames": total_frames,
            "fps": round(fps, 3),
            "duration_seconds": round((total_frames / fps), 3) if fps > 0 and total_frames > 0 else 0.0,
            "processed_frames": processed_frames,
            "processed_every_n_frames": processed_every_n_frames,
            "detected_frames": detected_frames,
            "stable_frames": stable_frames,
            "representative_frame_index": representative_frame_index,
            "representative_timestamp_seconds": representative_timestamp_seconds,
        }
        payload["recognized_plates"] = recognized_plates
        return payload

    def _process_video_upload_sync(
        app_state: Any,
        binary_stream: Any,
        filename: str,
        max_video_bytes: int,
    ) -> tuple[dict, int]:
        temp_token = uuid4().hex
        stream_key = f"video:{temp_token}"
        video_capture = None
        temp_path: Path | None = None

        try:
            temp_path = _stage_video_upload(
                app_state=app_state,
                binary_stream=binary_stream,
                filename=filename,
                max_video_bytes=max_video_bytes,
            )
            video_capture = cv2.VideoCapture(str(temp_path))
            if not video_capture.isOpened():
                return {"status": "error", "message": "Invalid video upload."}, 400

            video_settings = dict(app_state.settings.get("video_upload", {}))
            processed_every_n_frames = max(
                int(
                    video_settings.get(
                        "process_every_n_frames",
                        app_state.settings.get("stabilization", {}).get("process_every_n_frames", 3),
                    )
                ),
                1,
            )
            max_processed_frames = max(int(video_settings.get("max_processed_frames", 300)), 1)
            pipeline = app_state.pipeline
            fps = float(video_capture.get(cv2.CAP_PROP_FPS) or 0.0)
            total_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

            frame_index = -1
            processed_frames = 0
            detected_frames = 0
            stable_frames = 0
            recognized_plates: list[str] = []
            representative_payload: dict | None = None
            latest_payload: dict | None = None
            representative_rank = (-1, -1, -1, -1.0, -1.0)
            representative_frame_index: int | None = None
            representative_timestamp_seconds: float | None = None

            while processed_frames < max_processed_frames:
                ok, frame = video_capture.read()
                if not ok:
                    break

                frame_index += 1
                if frame_index % processed_every_n_frames != 0:
                    continue

                payload, annotated, crop = pipeline.process_frame(
                    frame,
                    source_type="video",
                    camera_role="upload",
                    source_name=filename,
                    stream_key=stream_key,
                )
                processed_frames += 1

                timestamp_seconds = round((frame_index / fps), 3) if fps > 0 else None
                payload["frame_index"] = frame_index
                payload["frame_timestamp_seconds"] = timestamp_seconds
                payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
                payload["crop_image_base64"] = pipeline.encode_image_base64(crop)

                latest_payload = payload
                if payload.get("plate_detected"):
                    detected_frames += 1

                stable = payload.get("stable_result") or {}
                stable_value = str(stable.get("value") or "").strip()
                if stable.get("accepted") and stable_value:
                    stable_frames += 1
                    if stable_value not in recognized_plates:
                        recognized_plates.append(stable_value)

                rank = _payload_rank(payload)
                if representative_payload is None or rank > representative_rank:
                    representative_payload = payload
                    representative_rank = rank
                    representative_frame_index = frame_index
                    representative_timestamp_seconds = timestamp_seconds

            if processed_frames == 0:
                return {"status": "error", "message": "Unable to read frames from uploaded video."}, 400

            chosen_payload = representative_payload or latest_payload
            status = "success" if detected_frames > 0 else "no_detection"
            message = (
                f"Processed {processed_frames} sampled frames from video."
                if detected_frames > 0
                else f"Processed {processed_frames} sampled frames but found no license plate."
            )
            response_payload = _video_response_from_payload(
                chosen_payload,
                filename=filename,
                status=status,
                message=message,
                total_frames=total_frames,
                fps=fps,
                processed_frames=processed_frames,
                processed_every_n_frames=processed_every_n_frames,
                detected_frames=detected_frames,
                stable_frames=stable_frames,
                recognized_plates=recognized_plates,
                representative_frame_index=representative_frame_index,
                representative_timestamp_seconds=representative_timestamp_seconds,
            )
            if detected_frames == 0:
                response_payload["annotated_image_base64"] = None
                response_payload["crop_image_base64"] = None

            return response_payload, 200
        finally:
            if video_capture is not None:
                video_capture.release()
            app_state.pipeline.clear_stream_state(stream_key)
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    @router.get("/")
    async def index(request: Request):
        settings = request.app.state.settings
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "app_title": settings["app"]["title"],
                "subtitle": settings["app"]["subtitle"],
                "university": settings["app"]["university"],
                "server_time": datetime.now(timezone.utc).isoformat(),
            },
        )

    @router.get("/settings")
    async def settings_page(request: Request):
        settings = request.app.state.settings
        return templates.TemplateResponse(
            request=request,
            name="settings.html",
            context={
                "app_title": settings["app"]["title"],
                "subtitle": settings["app"]["subtitle"],
                "university": settings["app"]["university"],
                "server_time": datetime.now(timezone.utc).isoformat(),
            },
        )

    @router.get("/artifacts")
    async def get_artifact(path: str = Query(..., min_length=1)):
        artifact_path = _resolve_artifact_path(path)
        return FileResponse(artifact_path)

    @router.get("/settings/cameras", response_model=CameraSettingsPayload)
    async def get_camera_settings(request: Request):
        return _camera_settings_payload(request)

    @router.put("/settings/cameras", response_model=CameraSettingsPayload)
    async def update_camera_settings(request: Request, payload: CameraSettingsUpdatePayload):
        settings = request.app.state.settings
        settings.setdefault("camera", {})
        settings.setdefault("cameras", {})
        settings["cameras"].setdefault("entry", {})
        settings["cameras"].setdefault("exit", {})

        entry_source = _normalize_camera_source(payload.entry_source)
        exit_source = _normalize_camera_source(payload.exit_source)

        settings["cameras"]["entry"]["source"] = entry_source
        settings["cameras"]["exit"]["source"] = exit_source
        settings["camera"]["source"] = entry_source

        persist_error = _persist_settings_file(request)
        restarted_roles, failed_roles = _apply_camera_settings(
            request,
            {
                "entry": entry_source,
                "exit": exit_source,
            },
        )

        response_payload = _camera_settings_payload(request)
        message_parts = ["Camera settings applied."]
        if persist_error:
            message_parts.append("Could not persist to YAML; changes are active only in memory.")
        if restarted_roles:
            message_parts.append(f"Restarted: {', '.join(restarted_roles)}.")
        if failed_roles:
            message_parts.append(f"Restart failed: {', '.join(failed_roles)}.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload

    @router.get("/settings/recognition", response_model=RecognitionSettingsPayload)
    async def get_recognition_settings(request: Request):
        return _recognition_settings_payload(request)

    @router.put("/settings/recognition", response_model=RecognitionSettingsPayload)
    async def update_recognition_settings(request: Request, payload: RecognitionSettingsUpdatePayload):
        detector_conf = min(max(float(payload.min_detector_confidence), 0.0), 1.0)
        ocr_conf = min(max(float(payload.min_ocr_confidence), 0.0), 1.0)
        stable_occurrences = max(int(payload.min_stable_occurrences), 1)
        max_threads = max(int(os.cpu_count() or 1), 1)
        ocr_cpu_threads = min(max(int(payload.ocr_cpu_threads), 1), max_threads)

        settings = request.app.state.settings
        settings.setdefault("session", {})
        settings.setdefault("stabilization", {})
        settings.setdefault("ocr", {})
        settings["session"]["min_detector_confidence"] = detector_conf
        settings["session"]["min_ocr_confidence"] = ocr_conf
        settings["session"]["min_stable_occurrences"] = stable_occurrences
        settings["stabilization"]["min_repetitions"] = stable_occurrences
        settings["ocr"]["cpu_threads"] = ocr_cpu_threads

        session_service = request.app.state.session_service
        session_service.min_detector_confidence = detector_conf
        session_service.min_ocr_confidence = ocr_conf
        session_service.min_stable_occurrences = stable_occurrences
        request.app.state.result_service.min_repetitions = stable_occurrences
        for camera in request.app.state.camera_services.values():
            tracker_service = getattr(camera, "tracker_service", None)
            if tracker_service is None:
                continue
            tracker_service.stop_ocr_after_stable_occurrences = stable_occurrences

        ocr_engine = request.app.state.ocr_engine
        ocr_reload_error: str | None = None
        try:
            ocr_engine.settings["cpu_threads"] = ocr_cpu_threads
            result_cache = getattr(ocr_engine, "result_cache", None)
            if result_cache is not None:
                result_cache.clear()
            if hasattr(ocr_engine, "_load"):
                ocr_engine._load()
            request.app.state.pipeline.settings["cpu_threads"] = ocr_cpu_threads
        except Exception as exc:
            ocr_reload_error = str(exc)

        persist_error = _persist_settings_file(request)

        response_payload = _recognition_settings_payload(request)
        message_parts = ["Recognition settings applied."]
        if ocr_reload_error:
            message_parts.append("OCR runtime reload failed; restart app to apply CPU core changes.")
        if persist_error:
            message_parts.append("YAML persist failed; changes are active only in memory.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload

    @router.get("/settings/detector-runtime", response_model=DetectorRuntimeSettingsPayload)
    async def get_detector_runtime_settings(request: Request):
        return _detector_runtime_settings_payload(request)

    @router.put("/settings/detector-runtime", response_model=DetectorRuntimeSettingsPayload)
    async def update_detector_runtime_settings(request: Request, payload: DetectorRuntimeSettingsUpdatePayload):
        backend = str(payload.backend or "ultralytics").strip().lower()
        if backend in {"onnx", "onnxruntime", "ort"}:
            backend = "onnxruntime"
        elif backend != "ultralytics":
            raise HTTPException(status_code=400, detail="Unsupported detector backend.")

        onnx_weights_path = str(payload.onnx_weights_path or "models/detector/best.onnx").strip()
        if not onnx_weights_path:
            onnx_weights_path = "models/detector/best.onnx"

        restarted_roles, failed_roles = _apply_detector_runtime_settings(
            request,
            backend=backend,
            onnx_weights_path=onnx_weights_path,
        )
        persist_error = _persist_settings_file(request)

        response_payload = _detector_runtime_settings_payload(request)
        message_parts = [f"Detector backend switched to {backend}."]
        if backend == "onnxruntime" and not request.app.state.detector.ready:
            message_parts.append(
                "ONNX Runtime detector is not ready yet. Check the ONNX file path and install onnxruntime."
            )
        if restarted_roles:
            message_parts.append(f"Restarted: {', '.join(restarted_roles)}.")
        if failed_roles:
            message_parts.append(f"Restart failed: {', '.join(failed_roles)}.")
        if persist_error:
            message_parts.append("Could not persist to YAML; changes are active only in memory.")
        response_payload["message"] = " ".join(message_parts)
        return response_payload

    @router.post("/predict/image", response_model=PipelinePayload)
    async def predict_image(request: Request, file: UploadFile = File(...)):
        filename = _safe_upload_name(file.filename, "uploaded_image.jpg")
        upload_settings = _upload_settings(request)
        allowed_image_extensions = _as_normalized_set(
            upload_settings.get("allowed_image_extensions"),
            (".jpg", ".jpeg", ".png", ".bmp", ".webp"),
        )
        allowed_image_mime_types = _as_normalized_set(
            upload_settings.get("allowed_image_mime_types"),
            ("image/jpeg", "image/png", "image/bmp", "image/webp"),
        )
        _validate_upload_type(
            upload=file,
            filename=filename,
            allowed_extensions=allowed_image_extensions,
            allowed_mime_types=allowed_image_mime_types,
            file_kind="image",
        )

        max_image_bytes = _resolve_max_upload_bytes(
            upload_settings,
            key="max_image_bytes",
            fallback=10 * 1024 * 1024,
        )
        try:
            content = await file.read(max_image_bytes + 1)
        finally:
            await file.close()

        if not content:
            raise HTTPException(status_code=400, detail="Empty image upload.")
        if len(content) > max_image_bytes:
            raise HTTPException(status_code=413, detail=f"Image upload exceeds {max_image_bytes} bytes.")

        image_array = np.frombuffer(content, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid image upload."})

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
        payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
        payload["crop_image_base64"] = pipeline.encode_image_base64(crop)
        request.app.state.latest_payload = payload
        request.app.state.latest_payloads["upload"] = payload
        _record_performance_snapshot(request, source="predict_image", force=True)
        return JSONResponse(content=payload)

    @router.post("/predict/video", response_model=VideoUploadPayload)
    async def predict_video(request: Request, file: UploadFile = File(...)):
        filename = _safe_upload_name(file.filename, "uploaded_video.mp4")
        upload_settings = _upload_settings(request)
        allowed_video_extensions = _as_normalized_set(
            upload_settings.get("allowed_video_extensions"),
            (".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"),
        )
        allowed_video_mime_types = _as_normalized_set(
            upload_settings.get("allowed_video_mime_types"),
            (
                "video/mp4",
                "video/x-msvideo",
                "video/quicktime",
                "video/x-matroska",
                "video/webm",
            ),
        )
        _validate_upload_type(
            upload=file,
            filename=filename,
            allowed_extensions=allowed_video_extensions,
            allowed_mime_types=allowed_video_mime_types,
            file_kind="video",
        )
        max_video_bytes = _resolve_max_upload_bytes(
            upload_settings,
            key="max_video_bytes",
            fallback=100 * 1024 * 1024,
        )

        try:
            try:
                response_payload, status_code = await asyncio.to_thread(
                    _process_video_upload_sync,
                    request.app.state,
                    file.file,
                    filename,
                    max_video_bytes,
                )
            except UploadSizeLimitExceededError as exc:
                raise HTTPException(status_code=413, detail=f"Video upload exceeds {exc.limit_bytes} bytes.") from exc

            if status_code == 200:
                request.app.state.latest_payload = response_payload
                request.app.state.latest_payloads["upload"] = response_payload
                _record_performance_snapshot(request, source="predict_video", force=True)
            return JSONResponse(status_code=status_code, content=response_payload)
        finally:
            await file.close()

    def _get_camera_or_404(request: Request, role: str):
        normalized_role = role.strip().lower()
        camera = request.app.state.camera_manager.get(normalized_role)
        if camera is None:
            raise HTTPException(status_code=404, detail=f"Unknown camera role: {role}")
        return camera

    def _latest_for_role(request: Request, role: str) -> dict:
        camera = _get_camera_or_404(request, role)
        latest_payloads = request.app.state.latest_payloads
        preferred_payload = camera.preferred_payload() if hasattr(camera, "preferred_payload") else None
        payload = preferred_payload or camera.latest_payload or latest_payloads.get(role)
        return payload or {
            "status": "idle",
            "message": f"No inference result available yet for role '{role}'.",
            "camera_role": role,
        }

    def _latest_payload_or_idle(request: Request) -> dict:
        payload = request.app.state.latest_payload
        if payload is not None:
            return payload
        default_role = request.app.state.default_camera_role
        role_payload = _latest_for_role(request, default_role)
        if role_payload.get("status") != "idle":
            return role_payload
        return {
            "status": "idle",
            "message": "No inference result available yet.",
        }

    def _status_payload(request: Request) -> dict[str, Any]:
        detector = request.app.state.detector
        ocr_engine = request.app.state.ocr_engine
        camera_manager = request.app.state.camera_manager
        storage_service = request.app.state.storage_service
        session_service = request.app.state.session_service
        latest_payload = request.app.state.latest_payload
        running_roles = camera_manager.running_roles()
        camera_details = {
            role: camera.snapshot()
            for role, camera in request.app.state.camera_services.items()
        }
        return {
            "server_time": datetime.now(timezone.utc).isoformat(),
            "app_title": request.app.state.settings["app"]["title"],
            "detector_ready": detector.ready,
            "detector_mode": detector.mode,
            "ocr_ready": ocr_engine.ready,
            "ocr_mode": ocr_engine.mode,
            "camera_running": bool(running_roles),
            "last_result_available": latest_payload is not None,
            "storage_ready": storage_service.ready,
            "storage_mode": storage_service.mode,
            "session_ready": session_service.ready,
            "session_mode": session_service.mode,
            "default_camera_role": camera_manager.default_role,
            "camera_roles": camera_manager.roles,
            "running_camera_roles": running_roles,
            "camera_details": camera_details,
        }

    def _latest_results_payload(request: Request) -> dict[str, Any]:
        latest_results: dict[str, Any] = {}
        stream_settings = request.app.state.settings.get("stream", {})
        include_sse_crop_base64 = bool(stream_settings.get("include_sse_crop_base64", True))
        for role, camera in request.app.state.camera_services.items():
            preferred_payload = camera.preferred_payload() if hasattr(camera, "preferred_payload") else None
            selected_payload = preferred_payload or camera.latest_payload or request.app.state.latest_payloads.get(role)
            if not isinstance(selected_payload, dict):
                latest_results[role] = selected_payload
                continue
            compact_payload = dict(selected_payload)
            compact_payload["annotated_image_base64"] = None
            if not include_sse_crop_base64:
                compact_payload["crop_image_base64"] = None
            latest_results[role] = compact_payload
        return latest_results

    def _as_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _payload_timing_snapshot(payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        timings = payload.get("timings_ms")
        if not isinstance(timings, dict):
            return None
        stable_result = payload.get("stable_result") or {}
        return {
            "detector": round(_as_float(timings.get("detector")), 3),
            "ocr": round(_as_float(timings.get("ocr")), 3),
            "pipeline": round(_as_float(timings.get("pipeline")), 3),
            "plate_detected": bool(payload.get("plate_detected")),
            "stable_accepted": bool(stable_result.get("accepted")),
            "status": str(payload.get("status", "")),
            "source_type": str(payload.get("source_type", "")),
            "camera_role": str(payload.get("camera_role", "")),
        }

    def _performance_snapshot(
        request: Request,
        source: str,
        status_payload: dict[str, Any] | None = None,
        active_sessions: int | None = None,
        recent_events: int | None = None,
        unmatched_exits: int | None = None,
    ) -> dict[str, Any]:
        status_row = status_payload or _status_payload(request)
        running_roles = [str(role) for role in status_row.get("running_camera_roles", [])]
        camera_details = status_row.get("camera_details")
        if not isinstance(camera_details, dict):
            camera_details = {}

        camera_fps: dict[str, dict[str, Any]] = {}
        for role, details in camera_details.items():
            details_map = details if isinstance(details, dict) else {}
            camera_fps[str(role)] = {
                "input_fps": round(_as_float(details_map.get("input_fps")), 3),
                "processed_fps": round(_as_float(details_map.get("processed_fps")), 3),
                "read_failures": int(details_map.get("read_failures") or 0),
                "uptime_seconds": round(_as_float(details_map.get("uptime_seconds")), 3),
                "last_start_error": details_map.get("last_start_error"),
            }

        latest_timings_ms: dict[str, dict[str, Any]] = {}
        for role, payload in _latest_results_payload(request).items():
            timing_row = _payload_timing_snapshot(payload)
            if timing_row is not None:
                latest_timings_ms[str(role)] = timing_row

        upload_payload = request.app.state.latest_payloads.get("upload")
        upload_timing = _payload_timing_snapshot(upload_payload)
        if upload_timing is not None:
            latest_timings_ms["upload"] = upload_timing

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "running_camera_count": len(running_roles),
            "running_camera_roles": running_roles,
            "detector_ready": bool(status_row.get("detector_ready")),
            "detector_mode": str(status_row.get("detector_mode", "unavailable")),
            "ocr_ready": bool(status_row.get("ocr_ready")),
            "ocr_mode": str(status_row.get("ocr_mode", "unavailable")),
            "storage_ready": bool(status_row.get("storage_ready")),
            "session_ready": bool(status_row.get("session_ready")),
            "camera_fps": camera_fps,
            "latest_timings_ms": latest_timings_ms,
            "active_sessions": active_sessions,
            "recent_events": recent_events,
            "unmatched_exits": unmatched_exits,
        }

    def _record_performance_snapshot(
        request: Request,
        source: str,
        *,
        force: bool = False,
        status_payload: dict[str, Any] | None = None,
        active_sessions: int | None = None,
        recent_events: int | None = None,
        unmatched_exits: int | None = None,
    ) -> None:
        performance_service = getattr(request.app.state, "performance_service", None)
        if performance_service is None:
            return

        snapshot = _performance_snapshot(
            request,
            source=source,
            status_payload=status_payload,
            active_sessions=active_sessions,
            recent_events=recent_events,
            unmatched_exits=unmatched_exits,
        )
        performance_service.append(snapshot, force=force)

    def _dashboard_stream_payload(request: Request) -> dict[str, Any]:
        nonlocal dashboard_cache_payload
        nonlocal dashboard_cache_updated_at

        dashboard_settings = dict(request.app.state.settings.get("dashboard_stream", {}))
        cache_ttl_seconds = max(float(dashboard_settings.get("cache_ttl_seconds", 0.5) or 0.5), 0.0)
        now = time.perf_counter()
        if dashboard_cache_payload is not None and (now - dashboard_cache_updated_at) <= cache_ttl_seconds:
            return dict(dashboard_cache_payload)

        session_service = request.app.state.session_service
        logging_service = request.app.state.logging_service
        active_limit = max(int(dashboard_settings.get("active_limit", 30) or 30), 1)
        event_limit = max(int(dashboard_settings.get("event_limit", 50) or 50), 1)
        log_limit = max(int(dashboard_settings.get("log_limit", 80) or 80), 1)
        history_limit = max(int(dashboard_settings.get("history_limit", 30) or 30), 1)
        unmatched_limit = max(int(dashboard_settings.get("unmatched_limit", 30) or 30), 1)

        payload = {
            "status": _status_payload(request),
            "active": session_service.get_active_sessions(limit=active_limit),
            "events": session_service.get_recent_events(
                limit=event_limit,
                include_unmatched=False,
                include_logged_only=False,
                include_ignored=False,
            ),
            "logs": logging_service.read_recent(limit=log_limit),
            "history": session_service.get_session_history(limit=history_limit),
            "unmatched": session_service.get_unmatched_exit_events(limit=unmatched_limit),
            "latest_results": _latest_results_payload(request),
        }
        _record_performance_snapshot(
            request,
            source="dashboard_stream",
            status_payload=payload["status"],
            active_sessions=len(payload["active"]),
            recent_events=len(payload["events"]),
            unmatched_exits=len(payload["unmatched"]),
        )
        dashboard_cache_payload = payload
        dashboard_cache_updated_at = now
        return payload

    @router.post("/cameras/{role}/start", response_model=CameraControlPayload)
    async def start_camera_by_role(request: Request, role: str):
        camera = _get_camera_or_404(request, role)
        started = camera.start()
        if started:
            _record_performance_snapshot(request, source=f"camera_start:{role}", force=True)
            return {
                "status": "running",
                "message": f"Camera '{role}' started.",
                "role": role,
                "error_code": None,
            }
        message, error_code = _camera_start_message(camera, role)
        return {
            "status": "error",
            "message": message,
            "role": role,
            "error_code": error_code,
        }

    @router.post("/cameras/{role}/stop", response_model=CameraControlPayload)
    async def stop_camera_by_role(request: Request, role: str):
        camera = _get_camera_or_404(request, role)
        camera.stop()
        _record_performance_snapshot(request, source=f"camera_stop:{role}", force=True)
        return {"status": "stopped", "message": f"Camera '{role}' stopped.", "role": role}

    @router.get("/cameras/{role}/stream")
    async def stream_by_role(request: Request, role: str):
        camera = _get_camera_or_404(request, role)
        return StreamingResponse(
            camera.stream_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/cameras/{role}/latest-result")
    async def latest_result_by_role(request: Request, role: str):
        return _latest_for_role(request, role)

    @router.post("/camera/start", response_model=CameraControlPayload)
    async def start_camera_compat(request: Request):
        default_role = request.app.state.default_camera_role
        return await start_camera_by_role(request, default_role)

    @router.post("/camera/stop", response_model=CameraControlPayload)
    async def stop_camera_compat(request: Request):
        default_role = request.app.state.default_camera_role
        return await stop_camera_by_role(request, default_role)

    @router.get("/stream")
    async def stream_compat(request: Request):
        default_role = request.app.state.default_camera_role
        return await stream_by_role(request, default_role)

    @router.get("/latest-result")
    async def latest_result_compat(request: Request):
        return _latest_payload_or_idle(request)

    @router.get("/status", response_model=AppStatusPayload)
    async def status(request: Request):
        status_row = _status_payload(request)
        _record_performance_snapshot(request, source="status_endpoint", status_payload=status_row)
        return status_row

    @router.get("/stream/dashboard-events")
    async def dashboard_events(request: Request):
        refresh_seconds = max(
            float(request.app.state.settings.get("app", {}).get("dashboard_refresh_seconds", 1.0) or 1.0),
            0.2,
        )

        async def event_generator():
            while True:
                payload = _dashboard_stream_payload(request)
                yield f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=True)}\n\n"
                try:
                    await asyncio.sleep(refresh_seconds)
                except asyncio.CancelledError:
                    break

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @router.get("/sessions/active", response_model=list[VehicleSessionPayload])
    async def active_sessions(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_active_sessions(limit=limit)

    @router.get("/sessions/history", response_model=list[VehicleSessionPayload])
    async def session_history(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_session_history(limit=limit)

    @router.get("/sessions/{session_id}", response_model=VehicleSessionPayload)
    async def one_session(request: Request, session_id: int):
        session = request.app.state.session_service.get_session(session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return session

    @router.get("/events/recent", response_model=list[RecognitionEventPayload])
    async def recent_events(
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
    async def unmatched_exit_events(request: Request, limit: int = Query(default=100, ge=1, le=500)):
        return request.app.state.session_service.get_unmatched_exit_events(limit=limit)

    @router.get("/performance/recent", response_model=list[PerformanceSnapshotPayload])
    async def performance_recent(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
        return request.app.state.performance_service.read_recent(limit=limit)

    @router.get("/performance/summary", response_model=PerformanceSummaryPayload)
    async def performance_summary(request: Request, limit: int = Query(default=240, ge=1, le=5000)):
        entries = request.app.state.performance_service.read_recent(limit=limit)
        return request.app.state.performance_service.summarize(entries)

    @router.delete("/moderation/events/{event_id}", response_model=ModerationActionPayload)
    async def delete_recognition_event(request: Request, event_id: int):
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
    async def delete_vehicle_session(request: Request, session_id: int):
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
    async def delete_unmatched_exit(request: Request, unmatched_exit_id: int):
        deleted = request.app.state.storage_service.delete_unmatched_exit(unmatched_exit_id=unmatched_exit_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Unmatched exit not found: {unmatched_exit_id}")
        return {
            "status": "deleted",
            "message": f"Unmatched exit {unmatched_exit_id} deleted.",
            "deleted_id": unmatched_exit_id,
            "entity_type": "unmatched_exit",
        }

    return router
