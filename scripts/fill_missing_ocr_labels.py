from __future__ import annotations

import argparse
import csv
from pathlib import Path

import easyocr
import numpy as np
from PIL import Image, ImageEnhance, ImageOps


ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
STOPWORDS = {"REGISTERED", "REGION", "PLATE", "HONDA", "PROVISEDE", "ROVISEDE", "IMPE", "REGL"}


def clean_text(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


def build_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    gray = image.convert("L")
    big = gray.resize((gray.width * 2, gray.height * 2), Image.Resampling.LANCZOS)
    enhanced = ImageEnhance.Contrast(ImageOps.autocontrast(big)).enhance(2.0)
    variants: list[tuple[str, Image.Image]] = [("base", enhanced)]
    if enhanced.height > enhanced.width:
        variants.append(("rot90", enhanced.rotate(90, expand=True)))
        variants.append(("rot270", enhanced.rotate(270, expand=True)))
    else:
        variants.append(("rot180", enhanced.rotate(180, expand=True)))
    return variants


def score_candidate(text: str, confidence: float) -> float:
    cleaned = clean_text(text)
    if not cleaned or cleaned in STOPWORDS:
        return 0.0

    score = float(confidence) * (1 + min(len(cleaned), 8) / 8)
    if len(cleaned) <= 1:
        score *= 0.2
    return score


def predict_text(
    reader: easyocr.Reader,
    image_path: Path,
) -> tuple[str, float, str]:
    image = Image.open(image_path).convert("RGB")
    best_text = ""
    best_score = 0.0
    best_variant = "none"

    for variant_name, variant_image in build_variants(image):
        results = reader.readtext(
            np.array(variant_image),
            detail=1,
            allowlist=ALLOWLIST,
            paragraph=False,
        )
        for _, text, confidence in results:
            cleaned = clean_text(text)
            score = score_candidate(cleaned, float(confidence))
            if score > best_score:
                best_text = cleaned
                best_score = score
                best_variant = variant_name

    return best_text, best_score, best_variant


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill missing OCR labels with EasyOCR guesses.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--model-dir", type=Path, default=Path("outputs/easyocr_model"))
    parser.add_argument("--user-dir", type=Path, default=Path("outputs/easyocr_user"))
    args = parser.parse_args()

    rows = list(csv.DictReader(args.input_csv.open(encoding="utf-8-sig")))
    subset = rows[args.start : args.start + args.limit]

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.model_dir.mkdir(parents=True, exist_ok=True)
    args.user_dir.mkdir(parents=True, exist_ok=True)

    reader = easyocr.Reader(
        ["en"],
        gpu=False,
        model_storage_directory=str(args.model_dir),
        user_network_directory=str(args.user_dir),
        verbose=False,
    )

    with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["image_path", "ocr_guess", "score", "variant"],
        )
        writer.writeheader()

        for row in subset:
            image_path = Path(row["image_path"])
            guess, score, variant = predict_text(reader, image_path)
            writer.writerow(
                {
                    "image_path": row["image_path"].replace("\\", "/"),
                    "ocr_guess": guess,
                    "score": f"{score:.4f}",
                    "variant": variant,
                }
            )
            print(f"{image_path.name},{guess},{score:.4f},{variant}")


if __name__ == "__main__":
    main()
