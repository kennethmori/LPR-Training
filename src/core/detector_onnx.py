from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from src.core.detector_postprocess import (
    postprocess_onnx_nms_output,
    postprocess_onnx_raw_output,
)

logger = logging.getLogger(__name__)

DEFAULT_ONNX_EXCEPTION_TYPES: tuple[type[BaseException], ...] = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    OSError,
)


def onnx_weights_path(weights_path: Path, settings: dict[str, Any]) -> Path:
    configured = settings.get("onnx_weights_path")
    if configured:
        return Path(str(configured))
    return weights_path.with_suffix(".onnx")


def load_onnxruntime_detector(
    *,
    weights_path: Path,
    settings: dict[str, Any],
    log_import_error: Callable[[], None],
    log_directml_retry: Callable[[], None],
) -> dict[str, Any]:
    onnx_path = onnx_weights_path(weights_path, settings)
    if not onnx_path.exists():
        return _load_state(mode="missing_onnx_weights")

    try:
        import onnxruntime as ort
    except (ImportError, OSError):
        log_import_error()
        return _load_state(mode="onnxruntime_not_installed")

    exception_types = resolve_onnx_exception_types(ort)
    try:
        configured_providers = resolve_onnx_providers(ort, settings)
        session = create_onnx_session(
            ort=ort,
            onnx_path=onnx_path,
            providers=configured_providers,
            exception_types=exception_types,
            settings=settings,
            log_directml_retry=log_directml_retry,
        )
        inputs = session.get_inputs()
        if not inputs:
            raise RuntimeError("onnx_input_missing")

        active_providers = list(session.get_providers())
        return {
            "model": session,
            "mode": format_onnx_mode(onnx_path=onnx_path, active_providers=active_providers),
            "ready": True,
            "onnx_input_name": inputs[0].name,
            "onnx_output_names": [output.name for output in session.get_outputs()],
            "onnx_available_providers": list(ort.get_available_providers()),
            "onnx_active_providers": active_providers,
            "onnx_exception_types": exception_types,
            "serialize_onnx_runs": uses_directml(active_providers),
        }
    except exception_types:
        logger.exception("Failed to initialize ONNX detector from '%s'.", onnx_path)
        return _load_state(mode="load_failed", exception_types=exception_types)


def _load_state(
    *,
    mode: str,
    exception_types: tuple[type[BaseException], ...] = DEFAULT_ONNX_EXCEPTION_TYPES,
) -> dict[str, Any]:
    return {
        "model": None,
        "mode": mode,
        "ready": False,
        "onnx_input_name": None,
        "onnx_output_names": None,
        "onnx_available_providers": [],
        "onnx_active_providers": [],
        "onnx_exception_types": exception_types,
        "serialize_onnx_runs": False,
    }


def create_onnx_session(
    *,
    ort: Any,
    onnx_path: Path,
    providers: list[str],
    exception_types: tuple[type[BaseException], ...],
    settings: dict[str, Any],
    log_directml_retry: Callable[[], None],
) -> Any:
    session_options = build_onnx_session_options(ort, providers=providers, settings=settings)
    try:
        return ort.InferenceSession(
            str(onnx_path),
            sess_options=session_options,
            providers=providers,
        )
    except exception_types:
        if not uses_directml(providers):
            raise

        log_directml_retry()
        cpu_providers = cpu_only_provider_list(ort.get_available_providers())
        if not cpu_providers:
            raise

        cpu_session_options = build_onnx_session_options(ort, providers=cpu_providers, settings=settings)
        return ort.InferenceSession(
            str(onnx_path),
            sess_options=cpu_session_options,
            providers=cpu_providers,
        )


def resolve_onnx_exception_types(ort: Any) -> tuple[type[BaseException], ...]:
    exception_types: list[type[BaseException]] = list(DEFAULT_ONNX_EXCEPTION_TYPES)
    pybind_state = getattr(getattr(ort, "capi", None), "onnxruntime_pybind11_state", None)
    for candidate_name in (
        "OnnxRuntimeError",
        "Fail",
        "InvalidArgument",
        "InvalidGraph",
        "NoModel",
        "NotImplemented",
        "RuntimeException",
    ):
        candidate = getattr(pybind_state, candidate_name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            exception_types.append(candidate)

    deduped: list[type[BaseException]] = []
    for exc_type in exception_types:
        if exc_type not in deduped:
            deduped.append(exc_type)
    return tuple(deduped)


def build_onnx_session_options(ort: Any, *, providers: list[str], settings: dict[str, Any]) -> Any:
    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    max_threads = max(int(os.cpu_count() or 1), 1)
    intra_op_threads = resolve_onnx_thread_count(
        settings.get("onnx_intra_op_threads"),
        max_threads=max_threads,
    )
    inter_op_threads = resolve_onnx_thread_count(
        settings.get("onnx_inter_op_threads"),
        max_threads=max_threads,
    )
    if intra_op_threads is not None:
        session_options.intra_op_num_threads = intra_op_threads
    if inter_op_threads is not None:
        session_options.inter_op_num_threads = inter_op_threads
    if uses_directml(providers):
        session_options.enable_mem_pattern = False
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return session_options


def resolve_onnx_providers(ort: Any, settings: dict[str, Any]) -> list[str]:
    available = list(ort.get_available_providers())
    configured = settings.get("onnx_execution_providers", "auto")

    if isinstance(configured, list):
        candidates = [str(item).strip() for item in configured if str(item).strip()]
    else:
        raw = str(configured or "auto").strip()
        if not raw or raw.lower() == "auto":
            candidates = [
                "TensorrtExecutionProvider",
                "CUDAExecutionProvider",
                "DmlExecutionProvider",
                "CPUExecutionProvider",
            ]
        else:
            candidates = [raw]

    providers = [provider for provider in candidates if provider in available]
    if not providers and "CPUExecutionProvider" in available:
        providers = ["CPUExecutionProvider"]
    return providers or available


def uses_directml(providers: list[str]) -> bool:
    return any(str(provider).strip() == "DmlExecutionProvider" for provider in providers)


def cpu_only_provider_list(available: list[str]) -> list[str]:
    if "CPUExecutionProvider" in available:
        return ["CPUExecutionProvider"]
    return []


def format_onnx_mode(onnx_path: Path, active_providers: list[str]) -> str:
    primary_provider = str(active_providers[0]).strip() if active_providers else "unknown_provider"
    return f"onnxruntime:{primary_provider}:{onnx_path.name}"


def resolve_onnx_thread_count(value: Any, *, max_threads: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None

    if parsed <= 0:
        return None
    return min(parsed, max_threads)


def detect_with_onnxruntime(
    *,
    model: Any,
    settings: dict[str, Any],
    image: np.ndarray,
    input_name: str | None,
    output_names: list[str] | None,
    exception_types: tuple[type[BaseException], ...],
    serialize_runs: bool,
    run_lock: Any,
    log_inference_error: Callable[[], None],
) -> list[dict[str, Any]]:
    if input_name is None:
        return []

    input_size = max(int(settings.get("input_size", 640) or 640), 32)
    tensor, scale, pad_left, pad_top = preprocess_for_onnx(image, input_size)

    try:
        if serialize_runs:
            with run_lock:
                outputs = model.run(output_names, {input_name: tensor})
        else:
            outputs = model.run(output_names, {input_name: tensor})
    except exception_types:
        log_inference_error()
        return []

    predictions = extract_onnx_predictions(outputs)
    if predictions.size == 0:
        return []

    if predictions.shape[1] in {6, 7}:
        detections = postprocess_onnx_nms_output(
            predictions=predictions,
            settings=settings,
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=image.shape,
        )
    else:
        detections = postprocess_onnx_raw_output(
            predictions=predictions,
            settings=settings,
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=image.shape,
        )

    detections.sort(key=lambda item: item["confidence"], reverse=True)
    max_detections = max(int(settings.get("max_detections", 5) or 5), 1)
    return detections[:max_detections]


def preprocess_for_onnx(image: np.ndarray, input_size: int) -> tuple[np.ndarray, float, int, int]:
    height, width = image.shape[:2]
    scale = min(input_size / max(width, 1), input_size / max(height, 1))
    resized_width = max(int(round(width * scale)), 1)
    resized_height = max(int(round(height * scale)), 1)

    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((input_size, input_size, 3), 114, dtype=np.uint8)
    pad_left = max((input_size - resized_width) // 2, 0)
    pad_top = max((input_size - resized_height) // 2, 0)
    canvas[pad_top:pad_top + resized_height, pad_left:pad_left + resized_width] = resized

    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
    return tensor, scale, pad_left, pad_top


def extract_onnx_predictions(outputs: list[Any]) -> np.ndarray:
    for output in outputs:
        array = np.asarray(output)
        if array.size == 0:
            continue

        if array.ndim == 3:
            array = array[0]
        if array.ndim == 1 and array.shape[0] in {6, 7}:
            return array.reshape(1, -1)
        if array.ndim != 2:
            continue

        if array.shape[1] in {6, 7}:
            return array.astype(np.float32)
        if array.shape[0] >= 5 and array.shape[0] < array.shape[1]:
            return array.T.astype(np.float32)
        return array.astype(np.float32)

    return np.empty((0, 0), dtype=np.float32)
