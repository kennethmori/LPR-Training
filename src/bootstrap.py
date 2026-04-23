from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.api.auth import AuthConfig
from src.config import AppConfig, load_app_config, load_settings_dict
from src.core.detector import PlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.pipeline import LicensePlatePipeline
from src.core.postprocess import PlateTextPostProcessor
from src.services.logging_service import LoggingService
from src.services.performance_service import PerformanceService
from src.services.result_service import ResultService
from src.services.session_service import SessionService
from src.services.storage_service import StorageService
from src.services.vehicle_registry_service import VehicleRegistryService


@dataclass(slots=True)
class CoreServices:
    detector_settings: dict[str, Any]
    tracking_settings: dict[str, Any]
    camera_settings_map: dict[str, dict[str, Any]]
    default_camera_role: str
    detector: PlateDetector
    ocr_engine: PlateOCREngine
    result_service: ResultService
    logging_service: LoggingService
    performance_service: PerformanceService
    storage_service: StorageService
    vehicle_registry_service: VehicleRegistryService
    session_service: SessionService
    pipeline: LicensePlatePipeline
    video_upload_dir: Path


def load_settings(config_path: Path) -> dict[str, Any]:
    return load_settings_dict(config_path)


def load_typed_settings(config_path: Path) -> AppConfig:
    return load_app_config(config_path)


def _coerce_app_config(settings: AppConfig | dict[str, Any]) -> AppConfig:
    if isinstance(settings, AppConfig):
        return settings
    return AppConfig.from_dict(settings)


def resolve_env_string(value: Any) -> str:
    if value is None:
        return ""
    candidate = str(value).strip()
    if not candidate:
        return ""
    if not candidate.lower().startswith("env:"):
        return candidate
    env_name = candidate[4:].strip()
    if not env_name:
        return ""
    return os.getenv(env_name, "").strip()


def build_auth_config(settings: AppConfig | dict[str, Any]) -> AuthConfig:
    config = _coerce_app_config(settings)
    auth_settings = config.auth.to_dict()
    return AuthConfig(
        enabled=bool(auth_settings.get("enabled", False)),
        admin_username=resolve_env_string(auth_settings.get("admin_username", "admin")) or "admin",
        admin_password=resolve_env_string(auth_settings.get("admin_password", "admin123")) or "admin123",
        session_secret=(
            resolve_env_string(auth_settings.get("session_secret", "plate-basic-admin-session-secret"))
            or "plate-basic-admin-session-secret"
        ),
        session_max_age=max(int(auth_settings.get("session_max_age_seconds", 43200) or 43200), 300),
    )


def resolve_camera_source_value(value: Any) -> Any:
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.lower().startswith("env:"):
            env_name = candidate[4:].strip()
            if not env_name:
                return None
            env_value = os.getenv(env_name, "").strip()
            if not env_value:
                return None
            if env_value.isdigit():
                return int(env_value)
            return env_value
        if candidate.isdigit():
            return int(candidate)
        return candidate
    return value


def build_camera_settings(settings: AppConfig | dict[str, Any]) -> dict[str, dict[str, Any]]:
    config = _coerce_app_config(settings)
    settings_dict = config.to_dict()
    if config.cameras:
        camera_map: dict[str, dict[str, Any]] = {}
        for role, role_settings in config.cameras.items():
            role_values = role_settings.to_dict()
            if "source" not in role_values and "source_index" in role_values:
                role_values["source"] = role_values["source_index"]
            if "source" in role_values:
                role_values["source"] = resolve_camera_source_value(role_values.get("source"))
            if "source" not in role_values:
                role_values["source"] = 0 if role == "entry" else 1
            camera_map[role] = role_values
        return camera_map

    fallback_settings = dict(settings_dict.get("camera", {}))
    if "source" not in fallback_settings:
        fallback_settings["source"] = fallback_settings.get("source_index", 0)
    fallback_settings["source"] = resolve_camera_source_value(fallback_settings.get("source"))
    return {"entry": fallback_settings}


def build_detector_settings(settings: AppConfig | dict[str, Any], base_dir: Path) -> dict[str, Any]:
    config = _coerce_app_config(settings)
    detector_settings = config.detector.to_dict()
    onnx_weights_path = detector_settings.get("onnx_weights_path")
    if onnx_weights_path:
        candidate = Path(str(onnx_weights_path))
        detector_settings["onnx_weights_path"] = str(
            candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()
        )
    return detector_settings


def build_detector(settings: AppConfig | dict[str, Any], base_dir: Path) -> PlateDetector:
    config = _coerce_app_config(settings)
    paths_settings = config.paths.to_dict()
    return PlateDetector(
        weights_path=base_dir / paths_settings["detector_weights"],
        settings=build_detector_settings(settings, base_dir),
    )


def build_core_services(settings: AppConfig | dict[str, Any], base_dir: Path) -> CoreServices:
    config = _coerce_app_config(settings)
    session_settings = config.session.to_dict()
    stabilization_settings = config.stabilization.to_dict()
    stabilization_min_repetitions = int(stabilization_settings.get("min_repetitions", 2) or 2)
    session_min_stable_occurrences = int(
        session_settings.get(
            "min_stable_occurrences",
            stabilization_min_repetitions,
        )
    )
    detector_settings = build_detector_settings(config, base_dir)
    ocr_settings = config.ocr.to_dict()
    for key in ("easyocr_model_dir", "easyocr_user_dir", "paddle_rec_model_dir"):
        value = ocr_settings.get(key)
        if value:
            ocr_settings[key] = str((base_dir / value).resolve())

    detector = build_detector(config, base_dir)
    ocr_engine = PlateOCREngine(ocr_settings)
    postprocessor = PlateTextPostProcessor(
        settings=config.postprocess.to_dict(),
        rules_path=base_dir / "configs" / "plate_rules.yaml",
    )
    result_service = ResultService(
        history_size=int(stabilization_settings["history_size"]),
        min_repetitions=stabilization_min_repetitions,
    )
    paths_settings = config.paths.to_dict()
    logging_service = LoggingService(log_path=base_dir / paths_settings["event_log_path"])
    performance_settings = config.performance.to_dict()
    performance_service = PerformanceService(
        log_path=base_dir / paths_settings.get("performance_log_path", "outputs/demo_logs/performance.jsonl"),
        min_interval_seconds=float(performance_settings.get("min_record_interval_seconds", 1.0) or 1.0),
        max_recent_entries=int(performance_settings.get("max_recent_entries", 5000) or 5000),
    )
    database_path = base_dir / paths_settings.get("database_path", "outputs/app_data/plate_events.db")
    video_upload_dir = base_dir / paths_settings.get("video_upload_dir", "outputs/app_data/video_uploads")
    video_upload_dir.mkdir(parents=True, exist_ok=True)
    storage_service = StorageService(db_path=database_path)
    vehicle_registry_settings = config.vehicle_registry.to_dict()
    vehicle_registry_service = VehicleRegistryService(
        storage_service=storage_service,
        enabled=bool(vehicle_registry_settings.get("enabled", True)),
        recent_history_limit=int(vehicle_registry_settings.get("recent_history_limit", 5) or 5),
    )
    session_service = SessionService(
        storage_service=storage_service,
        enabled=bool(session_settings.get("enabled", True)),
        cooldown_seconds=int(session_settings.get("cooldown_seconds", 15)),
        allow_only_one_open_session_per_plate=bool(
            session_settings.get("allow_only_one_open_session_per_plate", True)
        ),
        store_unmatched_exit_events=bool(session_settings.get("store_unmatched_exit_events", True)),
        min_detector_confidence=float(session_settings.get("min_detector_confidence", 0.5)),
        min_ocr_confidence=float(session_settings.get("min_ocr_confidence", 0.9)),
        min_stable_occurrences=session_min_stable_occurrences,
        ambiguity_window_seconds=int(session_settings.get("ambiguity_window_seconds", 30)),
        ambiguity_char_distance=int(session_settings.get("ambiguity_char_distance", 1)),
    )
    tracking_settings = config.tracking.to_dict()
    tracking_settings.setdefault(
        "stop_ocr_after_stable_occurrences",
        session_min_stable_occurrences,
    )
    tracking_settings.setdefault(
        "recognition_event_min_stable_occurrences",
        session_min_stable_occurrences,
    )

    pipeline = LicensePlatePipeline(
        detector=detector,
        ocr_engine=ocr_engine,
        postprocessor=postprocessor,
        result_service=result_service,
        logging_service=logging_service,
        settings={
            **detector_settings,
            **ocr_settings,
            **config.stabilization.to_dict(),
            **config.stream.to_dict(),
            **config.artifacts.to_dict(),
        },
        output_paths={
            "annotated": base_dir / paths_settings["annotated_output_dir"],
            "crops": base_dir / paths_settings["crop_output_dir"],
        },
    )

    return CoreServices(
        detector_settings=detector_settings,
        tracking_settings=tracking_settings,
        camera_settings_map=build_camera_settings(config),
        default_camera_role=str(config.app.default_camera_role or "entry").lower(),
        detector=detector,
        ocr_engine=ocr_engine,
        result_service=result_service,
        logging_service=logging_service,
        performance_service=performance_service,
        storage_service=storage_service,
        vehicle_registry_service=vehicle_registry_service,
        session_service=session_service,
        pipeline=pipeline,
        video_upload_dir=video_upload_dir,
    )
