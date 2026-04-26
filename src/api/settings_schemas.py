from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AppStatusPayload(BaseModel):
    server_time: str
    app_title: str
    detector_ready: bool
    detector_mode: str
    detector_execution_providers: list[str] = Field(default_factory=list)
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
    detector_confidence_threshold: float = 0.3
    detector_iou_threshold: float = 0.5
    detector_max_detections: int = 5
    min_detector_confidence_for_ocr: float = 0.55
    min_sharpness_for_ocr: float = 45.0
    ocr_cooldown_seconds: float = 0.75
    ocr_cpu_threads: int = 8
    updated_at: str | None = None
    message: str = ""


class RecognitionSettingsUpdatePayload(BaseModel):
    min_detector_confidence: float = 0.5
    min_ocr_confidence: float = 0.9
    min_stable_occurrences: int = 3
    detector_confidence_threshold: float = 0.3
    detector_iou_threshold: float = 0.5
    detector_max_detections: int = 5
    min_detector_confidence_for_ocr: float = 0.55
    min_sharpness_for_ocr: float = 45.0
    ocr_cooldown_seconds: float = 0.75
    ocr_cpu_threads: int = 8


class DetectorRuntimeSettingsPayload(BaseModel):
    backend: str = "ultralytics"
    detector_weights_path: str = "models/detector/yolo26nbest.pt"
    onnx_weights_path: str = "models/detector/yolo26nbest.onnx"
    onnx_provider_mode: str = "prefer_directml"
    onnx_execution_providers: list[str] = Field(default_factory=list)
    active_onnx_execution_providers: list[str] = Field(default_factory=list)
    available_pt_models: list[str] = Field(default_factory=list)
    available_onnx_models: list[str] = Field(default_factory=list)
    detector_ready: bool = False
    detector_mode: str = "unavailable"
    updated_at: str | None = None
    message: str = ""


class DetectorRuntimeSettingsUpdatePayload(BaseModel):
    backend: str = "ultralytics"
    detector_weights_path: str = "models/detector/yolo26nbest.pt"
    onnx_weights_path: str = "models/detector/yolo26nbest.onnx"
    onnx_provider_mode: str = "prefer_directml"


class CameraControlPayload(BaseModel):
    status: str
    message: str
    role: str
    error_code: str | None = None
