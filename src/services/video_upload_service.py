from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import cv2

from src.services.upload_validation import UploadProcessingError, UploadSizeLimitExceededError


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
            _unlink_quietly(candidate)
            raise
        except OSError as exc:
            _unlink_quietly(candidate)
            last_error = exc

    detail = f"Unable to stage uploaded video: {last_error}" if last_error else "Unable to stage uploaded video."
    raise UploadProcessingError(500, detail)


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


def _resolve_video_processing_settings(app_state: Any) -> tuple[int, int]:
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
    return processed_every_n_frames, max_processed_frames


def _add_video_frame_artifacts(
    *,
    pipeline: Any,
    payload: dict[str, Any],
    annotated: Any,
    crop: Any,
    frame_index: int,
    fps: float,
) -> float | None:
    timestamp_seconds = round((frame_index / fps), 3) if fps > 0 else None
    payload["frame_index"] = frame_index
    payload["frame_timestamp_seconds"] = timestamp_seconds
    payload["annotated_image_base64"] = pipeline.encode_image_base64(annotated)
    payload["crop_image_base64"] = pipeline.encode_image_base64(crop)
    return timestamp_seconds


def _update_video_stable_state(payload: dict[str, Any], recognized_plates: list[str]) -> int:
    stable = payload.get("stable_result") or {}
    stable_value = str(stable.get("value") or "").strip()
    if not stable.get("accepted") or not stable_value:
        return 0
    if stable_value not in recognized_plates:
        recognized_plates.append(stable_value)
    return 1


def _update_representative_payload(
    *,
    candidate_payload: dict[str, Any],
    candidate_frame_index: int,
    candidate_timestamp_seconds: float | None,
    current_payload: dict[str, Any] | None,
    current_rank: tuple[int, int, int, float, float],
    current_frame_index: int | None,
    current_timestamp_seconds: float | None,
) -> tuple[dict[str, Any] | None, tuple[int, int, int, float, float], int | None, float | None]:
    candidate_rank = _payload_rank(candidate_payload)
    if current_payload is None or candidate_rank > current_rank:
        return candidate_payload, candidate_rank, candidate_frame_index, candidate_timestamp_seconds
    return current_payload, current_rank, current_frame_index, current_timestamp_seconds


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
        temp_path = _stage_video_upload(app_state, binary_stream, filename, max_video_bytes)
        video_capture = cv2.VideoCapture(str(temp_path))
        if not video_capture.isOpened():
            return {"status": "error", "message": "Invalid video upload."}, 400

        processed_every_n_frames, max_processed_frames = _resolve_video_processing_settings(app_state)
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

            timestamp_seconds = _add_video_frame_artifacts(
                pipeline=pipeline,
                payload=payload,
                annotated=annotated,
                crop=crop,
                frame_index=frame_index,
                fps=fps,
            )

            latest_payload = payload
            detected_frames += int(bool(payload.get("plate_detected")))
            stable_frames += _update_video_stable_state(payload, recognized_plates)
            (
                representative_payload,
                representative_rank,
                representative_frame_index,
                representative_timestamp_seconds,
            ) = _update_representative_payload(
                candidate_payload=payload,
                candidate_frame_index=frame_index,
                candidate_timestamp_seconds=timestamp_seconds,
                current_payload=representative_payload,
                current_rank=representative_rank,
                current_frame_index=representative_frame_index,
                current_timestamp_seconds=representative_timestamp_seconds,
            )

        if processed_frames == 0:
            return {"status": "error", "message": "Unable to read frames from uploaded video."}, 400

        response_payload = _final_video_payload(
            representative_payload=representative_payload,
            latest_payload=latest_payload,
            filename=filename,
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
        return response_payload, 200
    finally:
        if video_capture is not None:
            video_capture.release()
        app_state.pipeline.clear_stream_state(stream_key)
        if temp_path is not None:
            _unlink_quietly(temp_path)


def _final_video_payload(
    *,
    representative_payload: dict[str, Any] | None,
    latest_payload: dict[str, Any] | None,
    filename: str,
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
    status = "success" if detected_frames > 0 else "no_detection"
    message = (
        f"Processed {processed_frames} sampled frames from video."
        if detected_frames > 0
        else f"Processed {processed_frames} sampled frames but found no license plate."
    )
    response_payload = _video_response_from_payload(
        representative_payload or latest_payload,
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
    return response_payload


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
