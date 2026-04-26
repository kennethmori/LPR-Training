from __future__ import annotations

from src.api.performance_schemas import PerformanceSnapshotPayload, PerformanceSummaryPayload
from src.api.recognition_schemas import (
    BoundingBox,
    DetectionPayload,
    EventRecord,
    OCRPayload,
    PipelinePayload,
    StableResultPayload,
    VideoSummaryPayload,
    VideoUploadPayload,
)
from src.api.session_schemas import (
    ManualOverrideRequestPayload,
    ManualOverrideResponsePayload,
    ModerationActionPayload,
    RecognitionEventPayload,
    UnmatchedExitEventPayload,
    VehicleSessionPayload,
)
from src.api.settings_schemas import (
    AppStatusPayload,
    CameraControlPayload,
    CameraSettingsPayload,
    CameraSettingsUpdatePayload,
    DetectorRuntimeSettingsPayload,
    DetectorRuntimeSettingsUpdatePayload,
    RecognitionSettingsPayload,
    RecognitionSettingsUpdatePayload,
)
from src.api.vehicle_schemas import (
    VehicleDocumentPayload,
    VehicleGateHistoryPayload,
    VehicleLookupPayload,
    VehicleProfilePayload,
)

__all__ = [
    "AppStatusPayload",
    "BoundingBox",
    "CameraControlPayload",
    "CameraSettingsPayload",
    "CameraSettingsUpdatePayload",
    "DetectionPayload",
    "DetectorRuntimeSettingsPayload",
    "DetectorRuntimeSettingsUpdatePayload",
    "EventRecord",
    "ManualOverrideRequestPayload",
    "ManualOverrideResponsePayload",
    "ModerationActionPayload",
    "OCRPayload",
    "PerformanceSnapshotPayload",
    "PerformanceSummaryPayload",
    "PipelinePayload",
    "RecognitionEventPayload",
    "RecognitionSettingsPayload",
    "RecognitionSettingsUpdatePayload",
    "StableResultPayload",
    "UnmatchedExitEventPayload",
    "VehicleDocumentPayload",
    "VehicleGateHistoryPayload",
    "VehicleLookupPayload",
    "VehicleProfilePayload",
    "VehicleSessionPayload",
    "VideoSummaryPayload",
    "VideoUploadPayload",
]
