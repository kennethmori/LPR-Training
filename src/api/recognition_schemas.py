from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.api.vehicle_schemas import VehicleLookupPayload


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
    vehicle_lookup: VehicleLookupPayload | None = None
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
