from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.api.vehicle_schemas import VehicleLookupPayload


class ModerationActionPayload(BaseModel):
    status: str
    message: str
    deleted_id: int
    entity_type: str


class ManualOverrideRequestPayload(BaseModel):
    plate_number: str
    action: str = "confirm_predicted"
    reason: str = ""
    camera_role: str = "entry"
    source_name: str = "manual_override"
    source_type: str = "manual_override"
    raw_text: str = ""
    cleaned_text: str = ""
    stable_text: str = ""
    detector_confidence: float = 1.0
    ocr_confidence: float = 1.0
    ocr_engine: str = "manual_override"
    crop_path: str | None = None
    annotated_frame_path: str | None = None


class ManualOverrideResponsePayload(BaseModel):
    status: str
    message: str
    recognition_event: dict[str, Any]
    session_result: dict[str, Any]
    vehicle_lookup: VehicleLookupPayload | None = None


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
    matched_vehicle_id: int | None = None
    matched_registration_status: str = ""
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
    matched_vehicle_id: int | None = None
    matched_registration_status: str = ""
    manual_verification_required: int = 0
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
