from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

from src.core.detector_onnx import (
    DEFAULT_ONNX_EXCEPTION_TYPES,
    build_onnx_session_options,
    cpu_only_provider_list,
    detect_with_onnxruntime,
    extract_onnx_predictions,
    format_onnx_mode,
    load_onnxruntime_detector,
    onnx_weights_path,
    preprocess_for_onnx,
    resolve_onnx_exception_types,
    resolve_onnx_providers,
    resolve_onnx_thread_count,
    uses_directml,
)
from src.core.detector_postprocess import (
    label_for_class,
    postprocess_onnx_nms_output,
    postprocess_onnx_raw_output,
    scale_xywh_to_original,
    scale_xyxy_to_original,
)
from src.core.detector_ultralytics import detect_with_ultralytics, load_ultralytics_detector

logger = logging.getLogger(__name__)


class PlateDetector:
    def __init__(self, weights_path: Path, settings: dict[str, Any]) -> None:
        self.weights_path = weights_path
        self.settings = settings
        self.model = None
        self.mode = "unavailable"
        self.ready = False
        self.backend = "ultralytics"
        self.onnx_input_name: str | None = None
        self.onnx_output_names: list[str] | None = None
        self.onnx_available_providers: list[str] = []
        self.onnx_active_providers: list[str] = []
        self._onnx_exception_types: tuple[type[BaseException], ...] = DEFAULT_ONNX_EXCEPTION_TYPES
        self._onnx_run_lock = Lock()
        self._serialize_onnx_runs = False
        self._last_error_log_at: dict[str, float] = {}
        self._load()

    def _load(self) -> None:
        backend = self._resolve_backend()
        self.backend = backend
        if backend == "onnxruntime":
            self._load_onnxruntime()
            return
        self._load_ultralytics()

    def _resolve_backend(self) -> str:
        backend = str(self.settings.get("backend", "ultralytics") or "ultralytics").strip().lower()
        if backend in {"onnx", "onnxruntime", "ort"}:
            return "onnxruntime"
        return "ultralytics"

    def _log_throttled_exception(self, key: str, message: str) -> None:
        interval_seconds = max(float(self.settings.get("error_log_interval_seconds", 5.0) or 5.0), 0.0)
        now = time.monotonic()
        last_logged_at = self._last_error_log_at.get(key)
        if last_logged_at is not None and interval_seconds > 0 and (now - last_logged_at) < interval_seconds:
            return
        self._last_error_log_at[key] = now
        logger.exception(message)

    def _load_ultralytics(self) -> None:
        self.model, self.mode, self.ready = load_ultralytics_detector(
            weights_path=self.weights_path,
            log_import_error=lambda: self._log_throttled_exception(
                "ultralytics_import",
                "Failed to import Ultralytics detector backend.",
            ),
        )

    def _load_onnxruntime(self) -> None:
        state = load_onnxruntime_detector(
            weights_path=self.weights_path,
            settings=self.settings,
            log_import_error=lambda: self._log_throttled_exception(
                "onnxruntime_import",
                "Failed to import ONNX Runtime detector backend.",
            ),
            log_directml_retry=lambda: self._log_throttled_exception(
                "onnx_directml_session_init",
                "DirectML ONNX session creation failed; retrying with CPUExecutionProvider.",
            ),
        )
        self.model = state["model"]
        self.mode = state["mode"]
        self.ready = state["ready"]
        self.onnx_input_name = state["onnx_input_name"]
        self.onnx_output_names = state["onnx_output_names"]
        self.onnx_available_providers = state["onnx_available_providers"]
        self.onnx_active_providers = state["onnx_active_providers"]
        self._onnx_exception_types = state["onnx_exception_types"]
        self._serialize_onnx_runs = state["serialize_onnx_runs"]

    def _create_onnx_session(self, ort: Any, onnx_path: Path, providers: list[str]) -> Any:
        from src.core.detector_onnx import create_onnx_session

        return create_onnx_session(
            ort=ort,
            onnx_path=onnx_path,
            providers=providers,
            exception_types=self._onnx_exception_types,
            settings=self.settings,
            log_directml_retry=lambda: self._log_throttled_exception(
                "onnx_directml_session_init",
                "DirectML ONNX session creation failed; retrying with CPUExecutionProvider.",
            ),
        )

    def _build_onnx_session_options(self, ort: Any, *, providers: list[str]) -> Any:
        return build_onnx_session_options(ort, providers=providers, settings=self.settings)

    def _resolve_onnx_providers(self, ort: Any) -> list[str]:
        return resolve_onnx_providers(ort, self.settings)

    def _onnx_weights_path(self) -> Path:
        return onnx_weights_path(self.weights_path, self.settings)

    def detect(self, image: np.ndarray) -> list[dict[str, Any]]:
        if not self.ready or self.model is None:
            return []

        if self.backend == "onnxruntime":
            return self._detect_with_onnxruntime(image)
        return self._detect_with_ultralytics(image)

    def _detect_with_ultralytics(self, image: np.ndarray) -> list[dict[str, Any]]:
        return detect_with_ultralytics(model=self.model, settings=self.settings, image=image)

    def _detect_with_onnxruntime(self, image: np.ndarray) -> list[dict[str, Any]]:
        return detect_with_onnxruntime(
            model=self.model,
            settings=self.settings,
            image=image,
            input_name=self.onnx_input_name,
            output_names=self.onnx_output_names,
            exception_types=self._onnx_exception_types,
            serialize_runs=self._serialize_onnx_runs,
            run_lock=self._onnx_run_lock,
            log_inference_error=lambda: self._log_throttled_exception(
                "onnx_inference",
                "ONNX detector inference failed.",
            ),
        )

    @staticmethod
    def _resolve_onnx_exception_types(ort: Any) -> tuple[type[BaseException], ...]:
        return resolve_onnx_exception_types(ort)

    @staticmethod
    def _uses_directml(providers: list[str]) -> bool:
        return uses_directml(providers)

    @staticmethod
    def _cpu_only_provider_list(available: list[str]) -> list[str]:
        return cpu_only_provider_list(available)

    @staticmethod
    def _format_onnx_mode(onnx_path: Path, active_providers: list[str]) -> str:
        return format_onnx_mode(onnx_path, active_providers)

    @staticmethod
    def _resolve_onnx_thread_count(value: Any, *, max_threads: int) -> int | None:
        return resolve_onnx_thread_count(value, max_threads=max_threads)

    @staticmethod
    def _preprocess_for_onnx(image: np.ndarray, input_size: int) -> tuple[np.ndarray, float, int, int]:
        return preprocess_for_onnx(image, input_size)

    @staticmethod
    def _extract_onnx_predictions(outputs: list[Any]) -> np.ndarray:
        return extract_onnx_predictions(outputs)

    def _postprocess_onnx_raw_output(
        self,
        predictions: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        return postprocess_onnx_raw_output(
            predictions=predictions,
            settings=self.settings,
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=original_shape,
        )

    def _postprocess_onnx_nms_output(
        self,
        predictions: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        return postprocess_onnx_nms_output(
            predictions=predictions,
            settings=self.settings,
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=original_shape,
        )

    @staticmethod
    def _scale_xywh_to_original(
        box: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> dict[str, int]:
        return scale_xywh_to_original(box, scale, pad_left, pad_top, original_shape)

    @staticmethod
    def _scale_xyxy_to_original(
        box: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> dict[str, int]:
        return scale_xyxy_to_original(box, scale, pad_left, pad_top, original_shape)

    def _label_for_class(self, class_index: int) -> str:
        return label_for_class(self.settings, class_index)
