from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from src.api.auth import AuthConfig, build_auth_cookie_value, is_valid_auth_cookie
from src.bootstrap import CoreServices
from src.config import AppConfig
from src.services.camera_manager import CameraManager
from src.services.camera_service import CameraService
from src.services.tracking_service import PlateTrackingService


@dataclass(slots=True)
class CameraRuntime:
    camera_services: dict[str, CameraService]
    camera_manager: CameraManager

    @property
    def default_camera_service(self) -> CameraService:
        return self.camera_manager.get(self.camera_manager.default_role)


def append_session_result_log(
    *,
    logging_service: Any,
    recognition_event: dict[str, Any] | None,
    session_result: dict[str, Any] | None,
) -> None:
    if not recognition_event or not session_result:
        return

    event_action = str(session_result.get("event_action", "") or "").strip().lower()
    if not event_action:
        return

    note_parts: list[str] = []
    status = str(session_result.get("status", "") or "").strip().lower()
    if status:
        note_parts.append(f"session_status={status}")

    reason = str(session_result.get("reason", "") or "").strip()
    if reason:
        note_parts.append(reason)

    recognition_event_id = session_result.get("recognition_event_id")
    if recognition_event_id is not None:
        note_parts.append(f"recognition_event_id={recognition_event_id}")

    session_id = session_result.get("session_id")
    if session_id is not None:
        note_parts.append(f"session_id={session_id}")

    unmatched_exit_id = session_result.get("unmatched_exit_id")
    if unmatched_exit_id is not None:
        note_parts.append(f"unmatched_exit_id={unmatched_exit_id}")

    logging_service.append(
        {
            "timestamp": recognition_event.get("timestamp"),
            "source_type": recognition_event.get("source_type", "camera"),
            "camera_role": recognition_event.get("camera_role", "unknown"),
            "source_name": recognition_event.get("source_name", ""),
            "plate_detected": True,
            "plate_number": recognition_event.get("plate_number", ""),
            "raw_text": recognition_event.get("raw_text", ""),
            "cleaned_text": recognition_event.get("cleaned_text", ""),
            "stable_text": recognition_event.get("stable_text", ""),
            "detector_confidence": float(recognition_event.get("detector_confidence", 0.0) or 0.0),
            "ocr_confidence": float(recognition_event.get("ocr_confidence", 0.0) or 0.0),
            "ocr_engine": recognition_event.get("ocr_engine", ""),
            "crop_path": recognition_event.get("crop_path"),
            "annotated_frame_path": recognition_event.get("annotated_frame_path"),
            "is_stable": bool(recognition_event.get("is_stable", False)),
            "event_action": event_action,
            "note": " | ".join(note_parts),
        }
    )


def make_payload_handler(app: FastAPI, services: CoreServices, role: str):
    def handler(payload: dict[str, Any]) -> None:
        session_result = None
        recognition_event = payload.get("recognition_event")
        if recognition_event:
            lookup_result = services.vehicle_registry_service.annotate_recognition_event(recognition_event)
            recognition_event = lookup_result["event"]
            payload["recognition_event"] = recognition_event
            payload["vehicle_lookup"] = lookup_result["vehicle_lookup"]
            session_result = services.session_service.process_recognition_event(recognition_event)
            append_session_result_log(
                logging_service=services.logging_service,
                recognition_event=recognition_event,
                session_result=session_result,
            )
        else:
            payload["vehicle_lookup"] = None
        payload["session_result"] = session_result
        app.state.latest_payloads[role] = payload
        app.state.latest_payload = payload

    return handler


def build_camera_runtime(app: FastAPI, services: CoreServices, settings: dict[str, Any]) -> CameraRuntime:
    camera_services: dict[str, CameraService] = {}
    for role, role_settings in services.camera_settings_map.items():
        merged_settings = {
            **settings.get("stream", {}),
            **settings.get("stabilization", {}),
            **services.tracking_settings,
            **role_settings,
        }
        source_name = str(merged_settings.get("source_name", f"{role}_camera"))
        tracker_service = PlateTrackingService(
            pipeline=services.pipeline,
            settings=merged_settings,
            camera_role=role,
            source_name=source_name,
        )
        camera_services[role] = CameraService(
            pipeline=services.pipeline,
            settings=merged_settings,
            camera_role=role,
            source_name=source_name,
            on_payload=make_payload_handler(app, services, role),
            tracker_service=tracker_service,
        )

    return CameraRuntime(
        camera_services=camera_services,
        camera_manager=CameraManager(
            camera_services=camera_services,
            default_role=services.default_camera_role,
        ),
    )


def install_app_state(
    app: FastAPI,
    *,
    settings: dict[str, Any],
    typed_settings: AppConfig,
    base_dir: Path,
    config_path: Path,
    auth_config: AuthConfig,
    services: CoreServices,
    camera_runtime: CameraRuntime,
) -> None:
    app.state.settings = settings
    app.state.app_config = typed_settings
    app.state.base_dir = base_dir
    app.state.config_path = config_path
    app.state.server_time_factory = lambda: datetime.now(timezone.utc).isoformat()
    app.state.auth_enabled = auth_config.enabled
    app.state.auth_admin_username = auth_config.admin_username
    app.state.auth_admin_password = auth_config.admin_password
    app.state.auth_cookie_name = auth_config.cookie_name
    app.state.auth_session_max_age = auth_config.session_max_age
    app.state.auth_issue_cookie_value = lambda: build_auth_cookie_value(
        auth_config.admin_username,
        auth_config.session_secret,
    )
    app.state.auth_is_valid_cookie = lambda cookie_value: is_valid_auth_cookie(
        cookie_value,
        auth_config.admin_username,
        auth_config.session_secret,
    )
    app.state.detector = services.detector
    app.state.detector_factory = type(services.detector)
    app.state.ocr_engine = services.ocr_engine
    app.state.result_service = services.result_service
    app.state.logging_service = services.logging_service
    app.state.performance_service = services.performance_service
    app.state.pipeline = services.pipeline
    app.state.storage_service = services.storage_service
    app.state.vehicle_registry_service = services.vehicle_registry_service
    app.state.session_service = services.session_service
    app.state.video_upload_dir = services.video_upload_dir
    app.state.camera_manager = camera_runtime.camera_manager
    app.state.camera_services = camera_runtime.camera_services
    app.state.camera_service = camera_runtime.default_camera_service
    app.state.default_camera_role = camera_runtime.camera_manager.default_role
    app.state.latest_payloads = {}
    app.state.latest_payload = None
