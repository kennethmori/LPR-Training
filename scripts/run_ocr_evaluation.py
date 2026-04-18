from __future__ import annotations

import argparse
from pathlib import Path

from evaluate_ocr import evaluate
from report_ocr_errors import build_error_report, write_summary
from run_ocr_predictions import BASE_DIR, export_predictions


def print_metrics(metrics: dict[str, float]) -> None:
    for key, value in metrics.items():
        print(f"{key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OCR predictions, score them, and write error reports.")
    parser.add_argument("crops_dir", type=Path)
    parser.add_argument("truth_csv", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=BASE_DIR / "outputs" / "ocr_eval",
        help="Directory for OCR evaluation outputs.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="Filename prefix for generated reports. Defaults to the truth CSV stem without _labels.",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=BASE_DIR / "configs" / "app_settings.yaml",
        help="Path to the app settings YAML.",
    )
    args = parser.parse_args()

    crops_dir = args.crops_dir.resolve()
    truth_csv = args.truth_csv.resolve()
    settings_path = args.settings.resolve()
    output_dir = args.output_dir.resolve()
    prefix = args.prefix or truth_csv.stem.replace("_labels", "")

    predictions_csv = output_dir / f"{prefix}_predictions.csv"
    merged_csv = output_dir / f"{prefix}_error_report.csv"
    errors_csv = output_dir / f"{prefix}_errors_only.csv"
    summary_txt = output_dir / f"{prefix}_error_summary.txt"

    export_result = export_predictions(
        crops_dir=crops_dir,
        output_csv=predictions_csv,
        settings_path=settings_path,
    )

    metrics = evaluate(truth_csv, predictions_csv)
    merged, errors_only, summary = build_error_report(truth_csv, predictions_csv)

    output_dir.mkdir(parents=True, exist_ok=True)
    merged.to_csv(merged_csv, index=False)
    errors_only.to_csv(errors_csv, index=False)
    write_summary(summary_txt, summary)

    print(f"Wrote {export_result['samples']} OCR predictions to {predictions_csv}")
    print(f"OCR mode: {export_result['ocr_mode']}")
    print_metrics(metrics)
    print(f"Wrote merged report to {merged_csv}")
    print(f"Wrote errors-only report to {errors_csv}")
    print(f"Wrote summary to {summary_txt}")


if __name__ == "__main__":
    main()
