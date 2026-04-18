from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent


def load_table(path: Path) -> pd.DataFrame:
    table = pd.read_csv(path)
    for column in ("image_path", "true_text", "predicted_text"):
        if column in table.columns:
            table[column] = table[column].fillna("").astype(str)
    if "confidence" in table.columns:
        table["confidence"] = pd.to_numeric(table["confidence"], errors="coerce").fillna(0.0)
    return table


def curate_confidence_dataset(
    truth_csv: Path,
    predictions_csv: Path,
    output_dir: Path,
    labels_csv: Path,
    manifest_csv: Path,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    require_exact_match: bool = False,
) -> dict[str, Any]:
    truth = load_table(truth_csv)
    predictions = load_table(predictions_csv)

    merged = truth.merge(predictions, on="image_path", how="inner", suffixes=("_truth", "_pred"))
    if merged.empty:
        raise ValueError("No overlapping image_path values between truth and predictions.")

    merged["exact_match"] = merged["true_text"] == merged["predicted_text"]

    selected = merged.copy()
    if min_confidence is not None:
        selected = selected[selected["confidence"] >= min_confidence].copy()
    if max_confidence is not None:
        selected = selected[selected["confidence"] <= max_confidence].copy()
    if require_exact_match:
        selected = selected[selected["exact_match"]].copy()

    selected.sort_values(by=["confidence", "image_path"], ascending=[False, True], inplace=True)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    labels_csv.parent.mkdir(parents=True, exist_ok=True)
    manifest_csv.parent.mkdir(parents=True, exist_ok=True)

    labels_rows: list[dict[str, str]] = []
    manifest_rows: list[dict[str, str]] = []

    for row in selected.itertuples(index=False):
        source_path = (BASE_DIR / row.image_path).resolve()
        if not source_path.exists():
            continue

        destination_path = output_dir / source_path.name
        shutil.copy2(source_path, destination_path)

        curated_rel = destination_path.relative_to(BASE_DIR).as_posix()
        labels_rows.append(
            {
                "image_path": curated_rel,
                "true_text": row.true_text,
            }
        )
        manifest_rows.append(
            {
                "source_image_path": row.image_path,
                "curated_image_path": curated_rel,
                "true_text": row.true_text,
                "predicted_text": row.predicted_text,
                "confidence": f"{float(row.confidence):.6f}",
                "engine": getattr(row, "engine", ""),
            }
        )

    with labels_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_path", "true_text"])
        writer.writeheader()
        writer.writerows(labels_rows)

    with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_image_path",
                "curated_image_path",
                "true_text",
                "predicted_text",
                "confidence",
                "engine",
            ],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    return {
        "selected": len(labels_rows),
        "output_dir": str(output_dir),
        "labels_csv": str(labels_csv),
        "manifest_csv": str(manifest_csv),
        "min_confidence": min_confidence,
        "max_confidence": max_confidence,
        "require_exact_match": require_exact_match,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a confidence-filtered OCR dataset for readable or weak samples.")
    parser.add_argument("truth_csv", type=Path, help="Ground-truth OCR labels CSV.")
    parser.add_argument("predictions_csv", type=Path, help="OCR predictions CSV.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for curated OCR crops.",
    )
    parser.add_argument(
        "--labels-csv",
        type=Path,
        required=True,
        help="Curated labels CSV to write.",
    )
    parser.add_argument(
        "--manifest-csv",
        type=Path,
        required=True,
        help="Detailed manifest CSV to write.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=None,
        help="Keep samples at or above this confidence.",
    )
    parser.add_argument(
        "--max-confidence",
        type=float,
        default=None,
        help="Keep samples at or below this confidence.",
    )
    parser.add_argument(
        "--require-exact-match",
        action="store_true",
        help="Keep only exact matches between truth and prediction.",
    )
    parser.add_argument(
        "--allow-mismatches",
        action="store_true",
        help="Allow OCR mismatches to remain in the curated set.",
    )
    args = parser.parse_args()

    result = curate_confidence_dataset(
        truth_csv=args.truth_csv.resolve(),
        predictions_csv=args.predictions_csv.resolve(),
        output_dir=args.output_dir.resolve(),
        labels_csv=args.labels_csv.resolve(),
        manifest_csv=args.manifest_csv.resolve(),
        min_confidence=args.min_confidence,
        max_confidence=args.max_confidence,
        require_exact_match=args.require_exact_match and not args.allow_mismatches,
    )

    print(f"Selected {result['selected']} crops")
    print(f"Output dir: {result['output_dir']}")
    print(f"Labels CSV: {result['labels_csv']}")
    print(f"Manifest CSV: {result['manifest_csv']}")


if __name__ == "__main__":
    main()
