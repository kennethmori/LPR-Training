from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import cv2
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core.cropper import resize_for_ocr
from src.core.ocr_engine import PlateOCREngine
from src.core.postprocess import PlateTextPostProcessor


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_settings(settings_path: Path) -> dict[str, Any]:
    with settings_path.open("r", encoding="utf-8") as handle:
        settings = yaml.safe_load(handle)
    ocr_settings = settings.get("ocr", {})
    for key in ("easyocr_model_dir", "easyocr_user_dir", "paddle_rec_model_dir"):
        value = ocr_settings.get(key)
        if value:
            ocr_settings[key] = str((BASE_DIR / value).resolve())
    return settings


def iter_images(crops_dir: Path) -> list[Path]:
    return sorted(path for path in crops_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def to_repo_relative(path: Path) -> str:
    try:
        return path.relative_to(BASE_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def export_predictions(crops_dir: Path, output_csv: Path, settings_path: Path) -> dict[str, Any]:
    if not crops_dir.exists() or not crops_dir.is_dir():
        raise FileNotFoundError(f"Crop directory not found: {crops_dir}")
    if not settings_path.exists():
        raise FileNotFoundError(f"Settings file not found: {settings_path}")

    settings = load_settings(settings_path)
    ocr_settings = settings.get("ocr", {})
    postprocess_settings = settings.get("postprocess", {})

    ocr_engine = PlateOCREngine(ocr_settings)
    postprocessor = PlateTextPostProcessor(
        settings=postprocess_settings,
        rules_path=BASE_DIR / "configs" / "plate_rules.yaml",
    )

    image_paths = iter_images(crops_dir)
    if not image_paths:
        raise ValueError(f"No crop images found in {crops_dir}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    resize_width = int(ocr_settings.get("resize_width", 320))

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_path", "predicted_text", "raw_text", "cleaned_text", "confidence", "engine"],
        )
        writer.writeheader()

        for image_path in image_paths:
            image = cv2.imread(str(image_path))
            if image is None:
                writer.writerow(
                    {
                        "image_path": to_repo_relative(image_path),
                        "predicted_text": "",
                        "raw_text": "",
                        "cleaned_text": "",
                        "confidence": "0.0",
                        "engine": "image_read_failed",
                    }
                )
                continue

            resized = resize_for_ocr(image, resize_width)
            ocr_result = ocr_engine.read(resized)
            cleaned_text = postprocessor.clean(ocr_result["raw_text"])

            writer.writerow(
                {
                    "image_path": to_repo_relative(image_path),
                    "predicted_text": cleaned_text,
                    "raw_text": ocr_result["raw_text"],
                    "cleaned_text": cleaned_text,
                    "confidence": f"{float(ocr_result['confidence']):.6f}",
                    "engine": ocr_result["engine"],
                }
            )

    return {
        "samples": len(image_paths),
        "output_csv": str(output_csv),
        "ocr_mode": ocr_engine.mode,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the current OCR stack over a crop folder and export predictions.")
    parser.add_argument("crops_dir", type=Path, help="Folder containing cropped plate images.")
    parser.add_argument("output_csv", type=Path, help="Where to write OCR predictions.")
    parser.add_argument(
        "--settings",
        type=Path,
        default=BASE_DIR / "configs" / "app_settings.yaml",
        help="Path to the app settings YAML.",
    )
    args = parser.parse_args()

    result = export_predictions(
        crops_dir=args.crops_dir.resolve(),
        output_csv=args.output_csv.resolve(),
        settings_path=args.settings.resolve(),
    )
    print(f"Wrote {result['samples']} OCR predictions to {result['output_csv']}")
    print(f"OCR mode: {result['ocr_mode']}")


if __name__ == "__main__":
    main()
