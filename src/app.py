from __future__ import annotations

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
from src.services.camera_service import CameraService
from src.services.logging_service import LoggingService
from src.services.result_service import ResultService


BASE_DIR = Path(__file__).resolve().parent.parent


def load_settings() -> dict[str, Any]:
    config_path = BASE_DIR / "configs" / "app_settings.yaml"
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title=settings["app"]["title"], debug=bool(settings["app"].get("debug", False)))

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    detector = PlateDetector(
        weights_path=BASE_DIR / settings["paths"]["detector_weights"],
        settings=settings["detector"],
    )
    ocr_engine = PlateOCREngine(settings["ocr"])
    postprocessor = PlateTextPostProcessor(
        settings=settings["postprocess"],
        rules_path=BASE_DIR / "configs" / "plate_rules.yaml",
    )
    result_service = ResultService(
        history_size=int(settings["stabilization"]["history_size"]),
        min_repetitions=int(settings["stabilization"]["min_repetitions"]),
    )
    logging_service = LoggingService(log_path=BASE_DIR / settings["paths"]["event_log_path"])
    pipeline = LicensePlatePipeline(
        detector=detector,
        ocr_engine=ocr_engine,
        postprocessor=postprocessor,
        result_service=result_service,
        logging_service=logging_service,
        settings={
            **settings["detector"],
            **settings["ocr"],
        },
        output_paths={
            "annotated": BASE_DIR / settings["paths"]["annotated_output_dir"],
            "crops": BASE_DIR / settings["paths"]["crop_output_dir"],
        },
    )
    camera_service = CameraService(
        pipeline=pipeline,
        settings={
            **settings["camera"],
            "process_every_n_frames": settings["stabilization"]["process_every_n_frames"],
        },
    )

    app.state.settings = settings
    app.state.detector = detector
    app.state.ocr_engine = ocr_engine
    app.state.pipeline = pipeline
    app.state.camera_service = camera_service
    app.state.latest_payload = None

    app.include_router(create_router(templates))
    return app


app = create_app()
