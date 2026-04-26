from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
