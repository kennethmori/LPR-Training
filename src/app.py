from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import create_router
from src.core.detector import PlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.pipeline import LicensePlatePipeline
from src.core.postprocess import PlateTextPostProcessor
from src.services.camera_manager import CameraManager
from src.services.camera_service import CameraService
from src.services.logging_service import LoggingService
from src.services.performance_service import PerformanceService
from src.services.result_service import ResultService
from src.services.session_service import SessionService
from src.services.storage_service import StorageService
from src.services.tracking_service import PlateTrackingService


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "app_settings.yaml"

# Paddle's source-hoster check adds noisy offline warnings and avoidable startup
# delay even when OCR models are already cached locally. Preserve any explicit
# user override, but default to the local-only path for this app.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def load_settings() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def build_camera_settings(settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if settings.get("cameras"):
        camera_map: dict[str, dict[str, Any]] = {}
        for role, role_settings in settings["cameras"].items():
            role_values = dict(role_settings or {})
            if "source" not in role_values and "source_index" in role_values:
                role_values["source"] = role_values["source_index"]
            if "source" in role_values:
                role_values["source"] = resolve_camera_source_value(role_values.get("source"))
            if "source" not in role_values:
                role_values["source"] = 0 if role == "entry" else 1
            camera_map[role] = role_values
        return camera_map

    fallback_settings = dict(settings.get("camera", {}))
    if "source" not in fallback_settings:
        fallback_settings["source"] = fallback_settings.get("source_index", 0)
    fallback_settings["source"] = resolve_camera_source_value(fallback_settings.get("source"))
    return {"entry": fallback_settings}


def build_detector_settings(settings: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    detector_settings = dict(settings["detector"])
    onnx_weights_path = detector_settings.get("onnx_weights_path")
    if onnx_weights_path:
        candidate = Path(str(onnx_weights_path))
        detector_settings["onnx_weights_path"] = str(
            candidate.resolve() if candidate.is_absolute() else (base_dir / candidate).resolve()
        )
    return detector_settings


def build_detector(settings: dict[str, Any], base_dir: Path) -> PlateDetector:
    return PlateDetector(
        weights_path=base_dir / settings["paths"]["detector_weights"],
        settings=build_detector_settings(settings, base_dir),
    )


def create_app() -> FastAPI:
    settings = load_settings()
    session_settings = dict(settings.get("session", {}))
    stable_occurrences_threshold = int(
        session_settings.get(
            "min_stable_occurrences",
            settings.get("stabilization", {}).get("min_repetitions", 2),
        )
    )
    settings.setdefault("stabilization", {})["min_repetitions"] = stable_occurrences_threshold
    detector_settings = build_detector_settings(settings, BASE_DIR)
    ocr_settings = dict(settings["ocr"])
    for key in ("easyocr_model_dir", "easyocr_user_dir", "paddle_rec_model_dir"):
        value = ocr_settings.get(key)
        if value:
            ocr_settings[key] = str((BASE_DIR / value).resolve())
    app = FastAPI(title=settings["app"]["title"], debug=bool(settings["app"].get("debug", False)))

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    detector = build_detector(settings, BASE_DIR)
    ocr_engine = PlateOCREngine(ocr_settings)
    postprocessor = PlateTextPostProcessor(
        settings=settings["postprocess"],
        rules_path=BASE_DIR / "configs" / "plate_rules.yaml",
    )
    result_service = ResultService(
        history_size=int(settings["stabilization"]["history_size"]),
        min_repetitions=stable_occurrences_threshold,
    )
    logging_service = LoggingService(log_path=BASE_DIR / settings["paths"]["event_log_path"])
    performance_settings = dict(settings.get("performance", {}))
    performance_service = PerformanceService(
        log_path=BASE_DIR / settings["paths"].get("performance_log_path", "outputs/demo_logs/performance.jsonl"),
        min_interval_seconds=float(performance_settings.get("min_record_interval_seconds", 1.0) or 1.0),
        max_recent_entries=int(performance_settings.get("max_recent_entries", 5000) or 5000),
    )
    database_path = BASE_DIR / settings["paths"].get("database_path", "outputs/app_data/plate_events.db")
    video_upload_dir = BASE_DIR / settings["paths"].get("video_upload_dir", "outputs/app_data/video_uploads")
    video_upload_dir.mkdir(parents=True, exist_ok=True)
    storage_service = StorageService(db_path=database_path)
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
        min_stable_occurrences=stable_occurrences_threshold,
        ambiguity_window_seconds=int(session_settings.get("ambiguity_window_seconds", 30)),
        ambiguity_char_distance=int(session_settings.get("ambiguity_char_distance", 1)),
    )
    tracking_settings = dict(settings.get("tracking", {}))
    tracking_settings.setdefault(
        "stop_ocr_after_stable_occurrences",
        stable_occurrences_threshold,
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
            **settings.get("stabilization", {}),
            **settings.get("stream", {}),
            **settings.get("artifacts", {}),
        },
        output_paths={
            "annotated": BASE_DIR / settings["paths"]["annotated_output_dir"],
            "crops": BASE_DIR / settings["paths"]["crop_output_dir"],
        },
    )

    camera_settings_map = build_camera_settings(settings)
    default_camera_role = str(settings.get("app", {}).get("default_camera_role", "entry")).lower()
    camera_services: dict[str, CameraService] = {}

    def make_payload_handler(role: str):
        def handler(payload: dict[str, Any]) -> None:
            session_result = None
            recognition_event = payload.get("recognition_event")
            if recognition_event:
                session_result = session_service.process_recognition_event(recognition_event)
            payload["session_result"] = session_result
            app.state.latest_payloads[role] = payload
            app.state.latest_payload = payload

        return handler

    for role, role_settings in camera_settings_map.items():
        merged_settings = {
            **settings.get("stream", {}),
            **settings.get("stabilization", {}),
            **tracking_settings,
            **role_settings,
        }
        tracker_service = PlateTrackingService(
            pipeline=pipeline,
            settings=merged_settings,
            camera_role=role,
            source_name=str(merged_settings.get("source_name", f"{role}_camera")),
        )
        camera_services[role] = CameraService(
            pipeline=pipeline,
            settings=merged_settings,
            camera_role=role,
            source_name=str(merged_settings.get("source_name", f"{role}_camera")),
            on_payload=make_payload_handler(role),
            tracker_service=tracker_service,
        )

    camera_manager = CameraManager(camera_services=camera_services, default_role=default_camera_role)
    camera_service = camera_manager.get(camera_manager.default_role)

    app.state.settings = settings
    app.state.base_dir = BASE_DIR
    app.state.config_path = CONFIG_PATH
    app.state.detector = detector
    app.state.ocr_engine = ocr_engine
    app.state.result_service = result_service
    app.state.logging_service = logging_service
    app.state.performance_service = performance_service
    app.state.pipeline = pipeline
    app.state.storage_service = storage_service
    app.state.session_service = session_service
    app.state.video_upload_dir = video_upload_dir
    app.state.camera_manager = camera_manager
    app.state.camera_services = camera_services
    app.state.camera_service = camera_service
    app.state.default_camera_role = camera_manager.default_role
    app.state.latest_payloads = {}
    app.state.latest_payload = None

    app.include_router(create_router(templates))

    @app.on_event("shutdown")
    def _shutdown() -> None:
        app.state.camera_manager.stop_all()

    return app


app = create_app()
