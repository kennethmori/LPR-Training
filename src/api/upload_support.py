from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2
from fastapi import HTTPException, Request, UploadFile

ARTIFACTS_ROOT = Path(__file__).resolve().parents[2] / "outputs"


class UploadSizeLimitExceededError(Exception):
    def __init__(self, limit_bytes: int) -> None:
        self.limit_bytes = int(limit_bytes)
        super().__init__(f"upload_size_limit_exceeded:{self.limit_bytes}")


def safe_upload_name(filename: str | None, fallback: str) -> str:
    candidate = (filename or "").strip()
    return candidate or fallback


def resolve_artifact_path(raw_path: str) -> Path:
    raw_candidate = str(raw_path or "").strip()
    if not raw_candidate:
        raise HTTPException(status_code=400, detail="Missing artifact path.")
    candidate = Path(raw_candidate)
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(ARTIFACTS_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Artifact path is outside outputs.") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return resolved


def upload_settings(request: Request) -> dict[str, Any]:
    return dict(request.app.state.settings.get("uploads", {}))


def as_normalized_set(values: Any, defaults: tuple[str, ...]) -> set[str]:
    if not isinstance(values, list):
        return set(defaults)
    normalized = {
        str(item).strip().lower()
        for item in values
        if str(item).strip()
    }
    return normalized or set(defaults)


def resolve_max_upload_bytes(settings: dict[str, Any], key: str, fallback: int) -> int:
    configured = int(settings.get(key, fallback) or fallback)
    return max(configured, 1)


def validate_upload_type(
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


def _payload_rank(payload: dict[str, Any]) -> tuple[int, int, int, float, float]:
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
    representative_payload: dict[str, Any] | None,
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
) -> dict[str, Any]:
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


def process_video_upload_sync(
    app_state: Any,
    binary_stream: Any,
    filename: str,
    max_video_bytes: int,
) -> tuple[dict[str, Any], int]:
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
        representative_payload: dict[str, Any] | None = None
        latest_payload: dict[str, Any] | None = None
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
