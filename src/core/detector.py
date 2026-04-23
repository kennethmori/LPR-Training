from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any

import cv2
import numpy as np

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
        self._onnx_exception_types: tuple[type[BaseException], ...] = (
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            OSError,
        )
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
        if not self.weights_path.exists():
            self.mode = "missing_weights"
            return

        try:
            from ultralytics import YOLO
        except (ImportError, OSError):
            self._log_throttled_exception(
                "ultralytics_import",
                "Failed to import Ultralytics detector backend.",
            )
            self.mode = "ultralytics_not_installed"
            return

        try:
            self.model = YOLO(str(self.weights_path))
            self.mode = "yolo"
            self.ready = True
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError):
            logger.exception("Failed to load Ultralytics detector weights from '%s'.", self.weights_path)
            self.model = None
            self.mode = "load_failed"
            self.ready = False

    def _load_onnxruntime(self) -> None:
        onnx_path = self._onnx_weights_path()
        if not onnx_path.exists():
            self.mode = "missing_onnx_weights"
            self.ready = False
            return

        try:
            import onnxruntime as ort
        except (ImportError, OSError):
            self._log_throttled_exception(
                "onnxruntime_import",
                "Failed to import ONNX Runtime detector backend.",
            )
            self.mode = "onnxruntime_not_installed"
            self.ready = False
            return

        self._onnx_exception_types = self._resolve_onnx_exception_types(ort)

        try:
            configured_providers = self._resolve_onnx_providers(ort)
            self.onnx_available_providers = list(ort.get_available_providers())
            session = self._create_onnx_session(
                ort=ort,
                onnx_path=onnx_path,
                providers=configured_providers,
            )
            inputs = session.get_inputs()
            if not inputs:
                raise RuntimeError("onnx_input_missing")

            self.model = session
            self.onnx_input_name = inputs[0].name
            self.onnx_output_names = [output.name for output in session.get_outputs()]
            self.onnx_active_providers = list(session.get_providers())
            self._serialize_onnx_runs = self._uses_directml(self.onnx_active_providers)
            self.mode = self._format_onnx_mode(
                onnx_path=onnx_path,
                active_providers=self.onnx_active_providers,
            )
            self.ready = True
        except self._onnx_exception_types:
            logger.exception("Failed to initialize ONNX detector from '%s'.", onnx_path)
            self.model = None
            self.onnx_input_name = None
            self.onnx_output_names = None
            self.onnx_available_providers = []
            self.onnx_active_providers = []
            self._serialize_onnx_runs = False
            self.mode = "load_failed"
            self.ready = False

    def _create_onnx_session(self, ort: Any, onnx_path: Path, providers: list[str]) -> Any:
        session_options = self._build_onnx_session_options(ort, providers=providers)
        try:
            return ort.InferenceSession(
                str(onnx_path),
                sess_options=session_options,
                providers=providers,
            )
        except self._onnx_exception_types:
            if not self._uses_directml(providers):
                raise

            self._log_throttled_exception(
                "onnx_directml_session_init",
                "DirectML ONNX session creation failed; retrying with CPUExecutionProvider.",
            )

            cpu_providers = self._cpu_only_provider_list(ort.get_available_providers())
            if not cpu_providers:
                raise

            cpu_session_options = self._build_onnx_session_options(ort, providers=cpu_providers)
            return ort.InferenceSession(
                str(onnx_path),
                sess_options=cpu_session_options,
                providers=cpu_providers,
            )

    @staticmethod
    def _resolve_onnx_exception_types(ort: Any) -> tuple[type[BaseException], ...]:
        exception_types: list[type[BaseException]] = [
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            OSError,
        ]

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

    def _build_onnx_session_options(self, ort: Any, *, providers: list[str]) -> Any:
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        max_threads = max(int(os.cpu_count() or 1), 1)
        intra_op_threads = self._resolve_onnx_thread_count(
            self.settings.get("onnx_intra_op_threads"),
            max_threads=max_threads,
        )
        inter_op_threads = self._resolve_onnx_thread_count(
            self.settings.get("onnx_inter_op_threads"),
            max_threads=max_threads,
        )
        if intra_op_threads is not None:
            session_options.intra_op_num_threads = intra_op_threads
        if inter_op_threads is not None:
            session_options.inter_op_num_threads = inter_op_threads
        if self._uses_directml(providers):
            session_options.enable_mem_pattern = False
            session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        return session_options

    def _resolve_onnx_providers(self, ort: Any) -> list[str]:
        available = list(ort.get_available_providers())
        configured = self.settings.get("onnx_execution_providers", "auto")

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

    @staticmethod
    def _uses_directml(providers: list[str]) -> bool:
        return any(str(provider).strip() == "DmlExecutionProvider" for provider in providers)

    @staticmethod
    def _cpu_only_provider_list(available: list[str]) -> list[str]:
        if "CPUExecutionProvider" in available:
            return ["CPUExecutionProvider"]
        return []

    @staticmethod
    def _format_onnx_mode(onnx_path: Path, active_providers: list[str]) -> str:
        primary_provider = str(active_providers[0]).strip() if active_providers else "unknown_provider"
        return f"onnxruntime:{primary_provider}:{onnx_path.name}"

    @staticmethod
    def _resolve_onnx_thread_count(value: Any, *, max_threads: int) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        if parsed <= 0:
            return None
        return min(parsed, max_threads)

    def _onnx_weights_path(self) -> Path:
        configured = self.settings.get("onnx_weights_path")
        if configured:
            return Path(str(configured))
        return self.weights_path.with_suffix(".onnx")

    def detect(self, image: np.ndarray) -> list[dict[str, Any]]:
        if not self.ready or self.model is None:
            return []

        if self.backend == "onnxruntime":
            return self._detect_with_onnxruntime(image)
        return self._detect_with_ultralytics(image)

    def _detect_with_ultralytics(self, image: np.ndarray) -> list[dict[str, Any]]:
        input_size = int(self.settings.get("input_size", 640) or 640)
        device = str(self.settings.get("device", "cpu") or "cpu")
        predictions = self.model.predict(
            source=image,
            conf=float(self.settings.get("confidence_threshold", 0.3)),
            iou=float(self.settings.get("iou_threshold", 0.5)),
            max_det=int(self.settings.get("max_detections", 5)),
            imgsz=input_size,
            device=device,
            verbose=False,
        )
        if not predictions:
            return []

        result = predictions[0]
        if getattr(result, "boxes", None) is None:
            return []

        detections: list[dict[str, Any]] = []
        names = getattr(result, "names", {0: "plate_number"})
        for box in result.boxes:
            xyxy = box.xyxy[0].tolist()
            confidence = float(box.conf[0].item())
            class_index = int(box.cls[0].item())
            detections.append(
                {
                    "bbox": {
                        "x1": int(xyxy[0]),
                        "y1": int(xyxy[1]),
                        "x2": int(xyxy[2]),
                        "y2": int(xyxy[3]),
                    },
                    "confidence": confidence,
                    "label": str(names.get(class_index, "plate_number")),
                }
            )

        detections.sort(key=lambda item: item["confidence"], reverse=True)
        return detections

    def _detect_with_onnxruntime(self, image: np.ndarray) -> list[dict[str, Any]]:
        if self.onnx_input_name is None:
            return []

        input_size = max(int(self.settings.get("input_size", 640) or 640), 32)
        tensor, scale, pad_left, pad_top = self._preprocess_for_onnx(image, input_size)

        try:
            if self._serialize_onnx_runs:
                with self._onnx_run_lock:
                    outputs = self.model.run(self.onnx_output_names, {self.onnx_input_name: tensor})
            else:
                outputs = self.model.run(self.onnx_output_names, {self.onnx_input_name: tensor})
        except self._onnx_exception_types:
            self._log_throttled_exception("onnx_inference", "ONNX detector inference failed.")
            return []

        predictions = self._extract_onnx_predictions(outputs)
        if predictions.size == 0:
            return []

        if predictions.shape[1] in {6, 7}:
            detections = self._postprocess_onnx_nms_output(
                predictions=predictions,
                scale=scale,
                pad_left=pad_left,
                pad_top=pad_top,
                original_shape=image.shape,
            )
        else:
            detections = self._postprocess_onnx_raw_output(
                predictions=predictions,
                scale=scale,
                pad_left=pad_left,
                pad_top=pad_top,
                original_shape=image.shape,
            )

        detections.sort(key=lambda item: item["confidence"], reverse=True)
        max_detections = max(int(self.settings.get("max_detections", 5) or 5), 1)
        return detections[:max_detections]

    @staticmethod
    def _preprocess_for_onnx(image: np.ndarray, input_size: int) -> tuple[np.ndarray, float, int, int]:
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

    @staticmethod
    def _extract_onnx_predictions(outputs: list[Any]) -> np.ndarray:
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

    def _postprocess_onnx_raw_output(
        self,
        predictions: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        if predictions.shape[1] <= 4:
            return []

        boxes_xywh = predictions[:, :4]
        class_scores = predictions[:, 4:]
        if class_scores.size == 0:
            return []

        class_indices = class_scores.argmax(axis=1)
        confidences = class_scores.max(axis=1)
        confidence_threshold = float(self.settings.get("confidence_threshold", 0.3))
        candidate_indices = np.where(confidences >= confidence_threshold)[0]
        if candidate_indices.size == 0:
            return []

        boxes_for_nms: list[list[int]] = []
        selected_scores: list[float] = []
        candidate_rows: list[tuple[int, dict[str, int], float]] = []

        for index in candidate_indices:
            bbox = self._scale_xywh_to_original(
                box=boxes_xywh[index],
                scale=scale,
                pad_left=pad_left,
                pad_top=pad_top,
                original_shape=original_shape,
            )
            width = max(bbox["x2"] - bbox["x1"], 1)
            height = max(bbox["y2"] - bbox["y1"], 1)
            boxes_for_nms.append([bbox["x1"], bbox["y1"], width, height])
            selected_scores.append(float(confidences[index]))
            candidate_rows.append((int(class_indices[index]), bbox, float(confidences[index])))

        kept_indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_for_nms,
            scores=selected_scores,
            score_threshold=confidence_threshold,
            nms_threshold=float(self.settings.get("iou_threshold", 0.5)),
        )
        if len(kept_indices) == 0:
            return []

        detections: list[dict[str, Any]] = []
        for kept_index in np.array(kept_indices).reshape(-1):
            class_index, bbox, confidence = candidate_rows[int(kept_index)]
            detections.append(
                {
                    "bbox": bbox,
                    "confidence": confidence,
                    "label": self._label_for_class(class_index),
                }
            )
        return detections

    def _postprocess_onnx_nms_output(
        self,
        predictions: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        confidence_threshold = float(self.settings.get("confidence_threshold", 0.3))
        boxes_for_nms: list[list[int]] = []
        selected_scores: list[float] = []
        candidate_rows: list[tuple[int, dict[str, int], float]] = []

        for row in predictions:
            if row.shape[0] < 6:
                continue
            confidence = float(row[4])
            if confidence < confidence_threshold:
                continue

            class_index = int(row[5]) if row.shape[0] > 5 else 0
            bbox = self._scale_xyxy_to_original(
                box=row[:4],
                scale=scale,
                pad_left=pad_left,
                pad_top=pad_top,
                original_shape=original_shape,
            )
            width = max(bbox["x2"] - bbox["x1"], 1)
            height = max(bbox["y2"] - bbox["y1"], 1)
            boxes_for_nms.append([bbox["x1"], bbox["y1"], width, height])
            selected_scores.append(confidence)
            candidate_rows.append((class_index, bbox, confidence))

        if not candidate_rows:
            return []

        # Some exported ONNX models still emit near-duplicate rows even in the
        # compact Nx6 format. Apply one more NMS pass to keep live tracking from
        # creating multiple overlapping tracks for the same plate.
        kept_indices = cv2.dnn.NMSBoxes(
            bboxes=boxes_for_nms,
            scores=selected_scores,
            score_threshold=confidence_threshold,
            nms_threshold=float(self.settings.get("iou_threshold", 0.5)),
        )
        if len(kept_indices) == 0:
            return []

        detections: list[dict[str, Any]] = []
        for kept_index in np.array(kept_indices).reshape(-1):
            class_index, bbox, confidence = candidate_rows[int(kept_index)]
            detections.append(
                {
                    "bbox": bbox,
                    "confidence": confidence,
                    "label": self._label_for_class(class_index),
                }
            )

        return detections

    @staticmethod
    def _scale_xywh_to_original(
        box: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> dict[str, int]:
        center_x, center_y, width, height = [float(value) for value in box.tolist()]
        x1 = center_x - (width / 2.0)
        y1 = center_y - (height / 2.0)
        x2 = center_x + (width / 2.0)
        y2 = center_y + (height / 2.0)
        return PlateDetector._scale_xyxy_to_original(
            box=np.asarray([x1, y1, x2, y2], dtype=np.float32),
            scale=scale,
            pad_left=pad_left,
            pad_top=pad_top,
            original_shape=original_shape,
        )

    @staticmethod
    def _scale_xyxy_to_original(
        box: np.ndarray,
        scale: float,
        pad_left: int,
        pad_top: int,
        original_shape: tuple[int, ...],
    ) -> dict[str, int]:
        original_height = int(original_shape[0])
        original_width = int(original_shape[1])
        x1, y1, x2, y2 = [float(value) for value in box.tolist()]

        x1 = (x1 - pad_left) / max(scale, 1e-6)
        y1 = (y1 - pad_top) / max(scale, 1e-6)
        x2 = (x2 - pad_left) / max(scale, 1e-6)
        y2 = (y2 - pad_top) / max(scale, 1e-6)

        x1 = int(np.clip(round(x1), 0, max(original_width - 1, 0)))
        y1 = int(np.clip(round(y1), 0, max(original_height - 1, 0)))
        x2 = int(np.clip(round(x2), x1 + 1, max(original_width, x1 + 1)))
        y2 = int(np.clip(round(y2), y1 + 1, max(original_height, y1 + 1)))

        return {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
        }

    def _label_for_class(self, class_index: int) -> str:
        configured = self.settings.get("class_names")
        if isinstance(configured, list) and 0 <= class_index < len(configured):
            return str(configured[class_index])
        return "plate_number"
