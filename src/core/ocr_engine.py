from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class PlateOCREngine:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.engine = None
        self.mode = "unavailable"
        self.ready = False
        self.cache_enabled = bool(self.settings.get("cache_enabled", False))
        self.cache_size = max(int(self.settings.get("cache_size", 128) or 128), 1)
        self.result_cache: OrderedDict[tuple[str, bytes], dict[str, Any]] = OrderedDict()
        self._load()

    def _load(self) -> None:
        preferred = str(self.settings.get("preferred_engine", "paddleocr")).lower()
        if preferred == "paddleocr" and self._load_paddleocr():
            return
        if self._load_easyocr():
            return
        self.mode = "ocr_dependencies_missing"
        self.ready = False

    def _load_paddleocr(self) -> bool:
        try:
            from paddleocr import PaddleOCR, TextRecognition
        except Exception:
            return False

        model_name = str(self.settings.get("paddle_rec_model_name", "en_PP-OCRv5_mobile_rec"))
        model_dir = self.settings.get("paddle_rec_model_dir")
        cpu_threads = int(self.settings.get("cpu_threads", 8))
        model_dir_value = None
        if model_dir:
            candidate_dir = Path(model_dir)
            if candidate_dir.exists():
                model_dir_value = str(candidate_dir)

        try:
            recognition_kwargs: dict[str, Any] = {
                "model_name": model_name,
                "device": "cpu",
                "cpu_threads": cpu_threads,
            }
            if model_dir_value:
                recognition_kwargs["model_dir"] = model_dir_value
            self.engine = TextRecognition(**recognition_kwargs)
            self.mode = f"paddleocr:{model_name}"
            self.ready = True
            return True
        except Exception:
            try:
                pipeline_kwargs: dict[str, Any] = {
                    "use_doc_orientation_classify": False,
                    "use_doc_unwarping": False,
                    "use_textline_orientation": False,
                    "text_recognition_model_name": model_name,
                    "device": "cpu",
                    "cpu_threads": cpu_threads,
                }
                if model_dir_value:
                    pipeline_kwargs["text_recognition_model_dir"] = model_dir_value
                self.engine = PaddleOCR(**pipeline_kwargs)
                self.mode = f"paddleocr:{model_name}"
                self.ready = True
                return True
            except Exception:
                self.engine = None
                return False

    def _load_easyocr(self) -> bool:
        fallback = str(self.settings.get("fallback_engine", "easyocr")).lower()
        if fallback != "easyocr":
            return False

        try:
            import easyocr
        except Exception:
            return False

        try:
            model_dir = self.settings.get("easyocr_model_dir")
            user_dir = self.settings.get("easyocr_user_dir")
            reader_kwargs: dict[str, Any] = {
                "gpu": False,
                "verbose": False,
            }
            if model_dir:
                reader_kwargs["model_storage_directory"] = str(Path(model_dir))
            if user_dir:
                reader_kwargs["user_network_directory"] = str(Path(user_dir))
            self.engine = easyocr.Reader(["en"], **reader_kwargs)
            self.mode = "easyocr"
            self.ready = True
            return True
        except Exception:
            self.engine = None
            return False

    def read(self, image: np.ndarray) -> dict[str, Any]:
        if not self.ready or self.engine is None:
            return {
                "raw_text": "",
                "confidence": 0.0,
                "engine": self.mode,
            }

        cache_key = self._build_cache_key(image)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result

        if self.mode.startswith("paddleocr"):
            result = self._read_with_paddleocr(image)
            self._store_cached_result(cache_key, result)
            return result
        if self.mode == "easyocr":
            result = self._read_with_easyocr(image)
            self._store_cached_result(cache_key, result)
            return result
        result = {
            "raw_text": "",
            "confidence": 0.0,
            "engine": self.mode,
        }
        self._store_cached_result(cache_key, result)
        return result

    def _build_cache_key(self, image: np.ndarray | None) -> tuple[str, bytes] | None:
        if not self.cache_enabled or image is None or getattr(image, "size", 0) == 0:
            return None

        signature_width = max(int(self.settings.get("cache_signature_width", 48) or 48), 8)
        signature_height = max(int(self.settings.get("cache_signature_height", 16) or 16), 8)
        quantization_levels = max(int(self.settings.get("cache_quantization_levels", 16) or 16), 2)

        if image.ndim == 3:
            grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            grayscale = image

        signature = cv2.resize(
            grayscale,
            (signature_width, signature_height),
            interpolation=cv2.INTER_AREA,
        )
        step = max(255 / (quantization_levels - 1), 1)
        quantized = np.rint(signature.astype(np.float32) / step).clip(0, quantization_levels - 1).astype(np.uint8)
        return (self.mode, quantized.tobytes())

    def _get_cached_result(self, cache_key: tuple[str, bytes] | None) -> dict[str, Any] | None:
        if cache_key is None:
            return None
        cached = self.result_cache.get(cache_key)
        if cached is None:
            return None
        self.result_cache.move_to_end(cache_key)
        return dict(cached)

    def _store_cached_result(self, cache_key: tuple[str, bytes] | None, result: dict[str, Any]) -> None:
        if cache_key is None:
            return
        self.result_cache[cache_key] = dict(result)
        self.result_cache.move_to_end(cache_key)
        while len(self.result_cache) > self.cache_size:
            self.result_cache.popitem(last=False)

    def _read_with_paddleocr(self, image: np.ndarray) -> dict[str, Any]:
        try:
            if hasattr(self.engine, "predict"):
                result = self.engine.predict(input=image)
                texts, scores = self._parse_paddle_predict_output(result)
            else:
                result = self.engine.ocr(image, cls=False)
                texts, scores = self._parse_paddle_legacy_output(result)
        except Exception:
            return {"raw_text": "", "confidence": 0.0, "engine": self.mode}

        raw_text = "".join(texts).strip()
        confidence = max(scores) if scores else 0.0
        return {"raw_text": raw_text, "confidence": float(confidence), "engine": self.mode}

    def _parse_paddle_predict_output(self, result: Any) -> tuple[list[str], list[float]]:
        texts: list[str] = []
        scores: list[float] = []

        if isinstance(result, list):
            for item in result:
                payload = item
                if hasattr(item, "res"):
                    payload = getattr(item, "res")
                if hasattr(item, "to_dict"):
                    try:
                        payload = item.to_dict()
                    except Exception:
                        payload = payload
                if isinstance(item, dict):
                    payload = item
                if isinstance(payload, dict) and "res" in payload and isinstance(payload["res"], dict):
                    payload = payload["res"]
                if isinstance(payload, dict):
                    rec_texts = payload.get("rec_texts") or []
                    rec_scores = payload.get("rec_scores") or []
                    if not rec_texts and payload.get("rec_text"):
                        rec_texts = [payload["rec_text"]]
                    if not rec_scores and payload.get("rec_score") is not None:
                        rec_scores = [payload["rec_score"]]
                    texts.extend([str(value) for value in rec_texts if value])
                    scores.extend([float(value) for value in rec_scores])
        return texts, scores

    def _parse_paddle_legacy_output(self, result: Any) -> tuple[list[str], list[float]]:
        texts: list[str] = []
        scores: list[float] = []

        if isinstance(result, list):
            for group in result:
                if not group:
                    continue
                for item in group:
                    if len(item) < 2:
                        continue
                    text, score = item[1]
                    texts.append(str(text))
                    scores.append(float(score))
        return texts, scores

    def _read_with_easyocr(self, image: np.ndarray) -> dict[str, Any]:
        try:
            result = self.engine.readtext(image, detail=1)
        except Exception:
            return {"raw_text": "", "confidence": 0.0, "engine": self.mode}

        texts = [str(item[1]) for item in result if len(item) >= 3]
        scores = [float(item[2]) for item in result if len(item) >= 3]
        raw_text = "".join(texts).strip()
        confidence = max(scores) if scores else 0.0
        return {"raw_text": raw_text, "confidence": float(confidence), "engine": self.mode}
