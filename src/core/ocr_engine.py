from __future__ import annotations

from typing import Any

import numpy as np


class PlateOCREngine:
    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.engine = None
        self.mode = "unavailable"
        self.ready = False
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
            from paddleocr import PaddleOCR
        except Exception:
            return False

        try:
            self.engine = PaddleOCR(
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
            self.mode = "paddleocr"
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
            self.engine = easyocr.Reader(["en"], gpu=False)
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

        if self.mode == "paddleocr":
            return self._read_with_paddleocr(image)
        if self.mode == "easyocr":
            return self._read_with_easyocr(image)
        return {
            "raw_text": "",
            "confidence": 0.0,
            "engine": self.mode,
        }

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
                if isinstance(item, dict):
                    rec_texts = item.get("rec_texts") or []
                    rec_scores = item.get("rec_scores") or []
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
