from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core.cropper import crop_plate, resize_for_ocr
from src.core.detector import PlateDetector
from src.core.ocr_engine import PlateOCREngine
from src.core.postprocess import PlateTextPostProcessor


def load_settings(settings_path: Path) -> dict[str, Any]:
    with settings_path.open("r", encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)
    ocr_settings = settings.get("ocr", {})
    for key in ("easyocr_model_dir", "easyocr_user_dir", "paddle_rec_model_dir"):
        value = ocr_settings.get(key)
        if value:
            ocr_settings[key] = str((BASE_DIR / value).resolve())
    return settings


def build_components(settings: dict[str, Any]) -> tuple[PlateDetector, PlateOCREngine, PlateTextPostProcessor]:
    detector = PlateDetector(
        weights_path=(BASE_DIR / settings["paths"]["detector_weights"]).resolve(),
        settings=settings["detector"],
    )
    ocr_engine = PlateOCREngine(settings["ocr"])
    postprocessor = PlateTextPostProcessor(
        settings=settings["postprocess"],
        rules_path=(BASE_DIR / "configs" / "plate_rules.yaml").resolve(),
    )
    return detector, ocr_engine, postprocessor


def run_end_to_end(
    manifest_csv: Path,
    output_csv: Path,
    settings_path: Path,
    single_target_only: bool = True,
) -> dict[str, Any]:
    settings = load_settings(settings_path)
    detector, ocr_engine, postprocessor = build_components(settings)
    manifest = pd.read_csv(manifest_csv)
    manifest["source_image_path"] = manifest["source_image_path"].fillna("").astype(str)
    manifest["true_text"] = manifest["true_text"].fillna("").astype(str)

    skipped_multi_target = 0
    if single_target_only:
        counts = manifest["source_image_path"].value_counts()
        allowed_paths = set(counts[counts == 1].index)
        skipped_multi_target = int(len(manifest) - manifest["source_image_path"].isin(allowed_paths).sum())
        manifest = manifest[manifest["source_image_path"].isin(allowed_paths)].copy()

    manifest = manifest.drop_duplicates(subset=["source_image_path"]).copy()
    manifest.sort_values(by=["split", "source_image_path"], inplace=True)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for row in manifest.itertuples(index=False):
        image_path = (BASE_DIR / row.source_image_path).resolve()
        image = cv2.imread(str(image_path))
        if image is None:
            results.append(
                {
                    "split": getattr(row, "split", ""),
                    "source_image_path": row.source_image_path,
                    "true_text": row.true_text,
                    "predicted_text": "",
                    "raw_text": "",
                    "detected": False,
                    "detector_confidence": 0.0,
                    "ocr_confidence": 0.0,
                    "detector_mode": detector.mode,
                    "ocr_mode": ocr_engine.mode,
                    "pipeline_time_ms": 0.0,
                    "note": "image_read_failed",
                }
            )
            continue

        started = time.perf_counter()
        detections = detector.detect(image)
        if not detections:
            results.append(
                {
                    "split": getattr(row, "split", ""),
                    "source_image_path": row.source_image_path,
                    "true_text": row.true_text,
                    "predicted_text": "",
                    "raw_text": "",
                    "detected": False,
                    "detector_confidence": 0.0,
                    "ocr_confidence": 0.0,
                    "detector_mode": detector.mode,
                    "ocr_mode": ocr_engine.mode,
                    "pipeline_time_ms": round((time.perf_counter() - started) * 1000, 2),
                    "note": "no_detection",
                }
            )
            continue

        best_detection = detections[0]
        crop, _ = crop_plate(
            image=image,
            bbox=best_detection["bbox"],
            padding_ratio=float(settings["detector"].get("padding_ratio", 0.05)),
        )
        resized_crop = resize_for_ocr(crop, int(settings["ocr"].get("resize_width", 320)))
        ocr_result = ocr_engine.read(resized_crop)
        cleaned_text = postprocessor.clean(ocr_result["raw_text"])

        results.append(
            {
                "split": getattr(row, "split", ""),
                "source_image_path": row.source_image_path,
                "true_text": row.true_text,
                "predicted_text": cleaned_text,
                "raw_text": ocr_result["raw_text"],
                "detected": True,
                "detector_confidence": float(best_detection["confidence"]),
                "ocr_confidence": float(ocr_result["confidence"]),
                "detector_mode": detector.mode,
                "ocr_mode": ocr_engine.mode,
                "pipeline_time_ms": round((time.perf_counter() - started) * 1000, 2),
                "note": "",
            }
        )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "split",
                "source_image_path",
                "true_text",
                "predicted_text",
                "raw_text",
                "detected",
                "detector_confidence",
                "ocr_confidence",
                "detector_mode",
                "ocr_mode",
                "pipeline_time_ms",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    return {
        "rows_written": len(results),
        "skipped_multi_target_rows": skipped_multi_target,
        "detector_mode": detector.mode,
        "ocr_mode": ocr_engine.mode,
        "output_csv": str(output_csv),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end detector plus OCR predictions over traced source images.")
    parser.add_argument("manifest_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument(
        "--settings",
        type=Path,
        default=BASE_DIR / "configs" / "app_settings.yaml",
        help="Path to the app settings YAML.",
    )
    parser.add_argument(
        "--include-multi-target",
        action="store_true",
        help="Allow source images that map to multiple curated crop truths.",
    )
    args = parser.parse_args()

    result = run_end_to_end(
        manifest_csv=args.manifest_csv.resolve(),
        output_csv=args.output_csv.resolve(),
        settings_path=args.settings.resolve(),
        single_target_only=not args.include_multi_target,
    )
    print(f"Wrote {result['rows_written']} end-to-end rows to {result['output_csv']}")
    print(f"Skipped multi-target rows: {result['skipped_multi_target_rows']}")
    print(f"Detector mode: {result['detector_mode']}")
    print(f"OCR mode: {result['ocr_mode']}")


if __name__ == "__main__":
    main()
