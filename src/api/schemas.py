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
    timings_ms: dict[str, float] = Field(default_factory=dict)


class AppStatusPayload(BaseModel):
    app_title: str
    detector_ready: bool
    detector_mode: str
    ocr_ready: bool
    ocr_mode: str
    camera_running: bool
    last_result_available: bool


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
