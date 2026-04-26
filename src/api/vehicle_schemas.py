from __future__ import annotations

from pydantic import BaseModel, Field


class VehicleDocumentPayload(BaseModel):
    document_id: int
    document_type: str = ""
    document_reference: str = ""
    file_ref: str | None = None
    verification_status: str = "pending"
    verified_at: str | None = None
    expires_at: str | None = None
    notes: str = ""


class VehicleGateHistoryPayload(BaseModel):
    id: int
    timestamp: str | None = None
    camera_role: str = ""
    event_action: str = ""
    note: str = ""
    ocr_confidence: float = 0.0
    detector_confidence: float = 0.0


class VehicleProfilePayload(BaseModel):
    vehicle_id: int
    plate_number: str = ""
    owner_name: str = ""
    user_category: str = ""
    owner_affiliation: str = ""
    owner_reference: str = ""
    vehicle_type: str = ""
    vehicle_brand: str = ""
    vehicle_model: str = ""
    vehicle_color: str = ""
    registration_status: str = "pending"
    approval_date: str | None = None
    expiry_date: str | None = None
    status_notes: str = ""
    record_source: str = ""
    profile_photo_url: str = ""


class VehicleLookupPayload(BaseModel):
    matched: bool = False
    lookup_outcome: str = "visitor_unregistered"
    plate_number: str = ""
    registration_status: str = "unknown"
    manual_verification_required: bool = True
    status_message: str = ""
    profile: VehicleProfilePayload | None = None
    documents: list[VehicleDocumentPayload] = Field(default_factory=list)
    recent_history: list[VehicleGateHistoryPayload] = Field(default_factory=list)
