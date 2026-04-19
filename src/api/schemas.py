from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class DetectionPayload(BaseModel):
    bbox: BoundingBox
    confidence: float
    label: str = "plate_number"


class OCRPayload(BaseModel):
    raw_text: str = ""
    cleaned_text: str = ""
    confidence: float = 0.0
    engine: str = "unavailable"


class StableResultPayload(BaseModel):
    value: str = ""
    confidence: float = 0.0
    occurrences: int = 0
    accepted: bool = False


class PipelinePayload(BaseModel):
    source_type: str
    camera_role: str = "upload"
    source_name: str = "upload_image"
    status: str
    message: str
    detector_mode: str = "unavailable"
    ocr_mode: str = "unavailable"
    detection: DetectionPayload | None = None
    ocr: OCRPayload | None = None
    stable_result: StableResultPayload | None = None
    plate_detected: bool = False
    timestamp: str
    annotated_image_base64: str | None = None
    crop_image_base64: str | None = None
    recognition_event: dict[str, Any] | None = None
    session_result: dict[str, Any] | None = None
    timings_ms: dict[str, float] = Field(default_factory=dict)


class VideoSummaryPayload(BaseModel):
    total_frames: int = 0
    fps: float = 0.0
    duration_seconds: float = 0.0
    processed_frames: int = 0
    processed_every_n_frames: int = 1
    detected_frames: int = 0
    stable_frames: int = 0
    representative_frame_index: int | None = None
    representative_timestamp_seconds: float | None = None


class VideoUploadPayload(PipelinePayload):
    video_summary: VideoSummaryPayload = Field(default_factory=VideoSummaryPayload)
    recognized_plates: list[str] = Field(default_factory=list)


class AppStatusPayload(BaseModel):
    server_time: str
    app_title: str
    detector_ready: bool
    detector_mode: str
    ocr_ready: bool
    ocr_mode: str
    camera_running: bool
    last_result_available: bool
    storage_ready: bool = False
    storage_mode: str = "unavailable"
    session_ready: bool = False
    session_mode: str = "disabled_or_unavailable"
    default_camera_role: str = "entry"
    camera_roles: list[str] = Field(default_factory=list)
    running_camera_roles: list[str] = Field(default_factory=list)
    camera_details: dict[str, Any] = Field(default_factory=dict)


class CameraSettingsPayload(BaseModel):
    entry_source: str = ""
    exit_source: str = ""
    fallback_source: str = ""
    updated_at: str | None = None
    message: str = ""


class CameraSettingsUpdatePayload(BaseModel):
    entry_source: str = ""
    exit_source: str = ""


class RecognitionSettingsPayload(BaseModel):
    min_detector_confidence: float = 0.5
    min_ocr_confidence: float = 0.9
    min_stable_occurrences: int = 3
    ocr_cpu_threads: int = 8
    updated_at: str | None = None
    message: str = ""


class RecognitionSettingsUpdatePayload(BaseModel):
    min_detector_confidence: float = 0.5
    min_ocr_confidence: float = 0.9
    min_stable_occurrences: int = 3
    ocr_cpu_threads: int = 8


class DetectorRuntimeSettingsPayload(BaseModel):
    backend: str = "ultralytics"
    onnx_weights_path: str = "models/detector/best.onnx"
    detector_ready: bool = False
    detector_mode: str = "unavailable"
    updated_at: str | None = None
    message: str = ""


class DetectorRuntimeSettingsUpdatePayload(BaseModel):
    backend: str = "ultralytics"
    onnx_weights_path: str = "models/detector/best.onnx"
    ocr_cpu_threads: int = 8


class EventRecord(BaseModel):
    timestamp: str
    source_type: str
    plate_detected: bool
    detector_confidence: float = 0.0
    ocr_confidence: float = 0.0
    raw_text: str = ""
    cleaned_text: str = ""
    stable_text: str = ""
    timings_ms: dict[str, float] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class CameraControlPayload(BaseModel):
    status: str
    message: str
    role: str
    error_code: str | None = None


class ModerationActionPayload(BaseModel):
    status: str
    message: str
    deleted_id: int
    entity_type: str


class VehicleSessionPayload(BaseModel):
    id: int
    plate_number: str
    status: str
    entry_time: str
    exit_time: str | None = None
    entry_camera: str | None = None
    exit_camera: str | None = None
    entry_event_id: int | None = None
    exit_event_id: int | None = None
    entry_confidence: float = 0.0
    exit_confidence: float = 0.0
    entry_crop_path: str | None = None
    exit_crop_path: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str


class RecognitionEventPayload(BaseModel):
    id: int
    timestamp: str
    camera_role: str
    source_name: str | None = None
    source_type: str
    raw_text: str = ""
    cleaned_text: str = ""
    stable_text: str = ""
    plate_number: str = ""
    detector_confidence: float = 0.0
    ocr_confidence: float = 0.0
    ocr_engine: str = ""
    crop_path: str | None = None
    annotated_frame_path: str | None = None
    is_stable: int = 0
    event_action: str = "logged_only"
    created_session_id: int | None = None
    closed_session_id: int | None = None
    note: str = ""


class UnmatchedExitEventPayload(BaseModel):
    id: int
    recognition_event_id: int
    plate_number: str
    timestamp: str
    camera_role: str
    reason: str
    resolved: int
    notes: str = ""


class PerformanceSnapshotPayload(BaseModel):
    timestamp: str
    source: str = ""
    running_camera_count: int = 0
    running_camera_roles: list[str] = Field(default_factory=list)
    detector_ready: bool = False
    detector_mode: str = "unavailable"
    ocr_ready: bool = False
    ocr_mode: str = "unavailable"
    storage_ready: bool = False
    session_ready: bool = False
    camera_fps: dict[str, dict[str, Any]] = Field(default_factory=dict)
    latest_timings_ms: dict[str, dict[str, Any]] = Field(default_factory=dict)
    active_sessions: int | None = None
    recent_events: int | None = None
    unmatched_exits: int | None = None
    log_id: str | None = None
    log_source: str | None = None


class PerformanceSummaryPayload(BaseModel):
    sample_count: int = 0
    from_timestamp: str | None = None
    to_timestamp: str | None = None
    avg_running_cameras: float = 0.0
    avg_input_fps_by_role: dict[str, float] = Field(default_factory=dict)
    avg_processed_fps_by_role: dict[str, float] = Field(default_factory=dict)
    avg_pipeline_ms_by_stream: dict[str, float] = Field(default_factory=dict)
