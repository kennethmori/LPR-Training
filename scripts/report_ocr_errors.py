from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import pandas as pd
from evaluate_ocr import levenshtein_distance

CONFUSION_PAIRS = [
    ("0", "O"),
    ("O", "0"),
    ("U", "V"),
    ("V", "U"),
    ("M", "H"),
    ("H", "M"),
    ("8", "B"),
    ("B", "8"),
]


def optional_series(frame: pd.DataFrame, column: str, default: object) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    return pd.Series([default] * len(frame), index=frame.index)


def build_error_report(truth_path: Path, predictions_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    truth = pd.read_csv(truth_path)
    predictions = pd.read_csv(predictions_path)
    merged = truth.merge(predictions, on="image_path", how="inner")
    if merged.empty:
        raise ValueError("No overlapping image_path values between truth and predictions.")

    merged["true_text"] = merged["true_text"].fillna("").astype(str)
    merged["predicted_text"] = merged["predicted_text"].fillna("").astype(str)
    merged["raw_text"] = optional_series(merged, "raw_text", "").fillna("").astype(str)
    merged["cleaned_text"] = optional_series(merged, "cleaned_text", "").fillna("").astype(str)
    merged["confidence"] = pd.to_numeric(optional_series(merged, "confidence", 0.0), errors="coerce").fillna(0.0)
    merged["engine"] = optional_series(merged, "engine", "").fillna("").astype(str)
    merged["exact_match"] = merged["true_text"] == merged["predicted_text"]
    merged["edit_distance"] = merged.apply(
        lambda row: levenshtein_distance(row["true_text"], row["predicted_text"]),
        axis=1,
    )
    merged["true_length"] = merged["true_text"].str.len()
    merged["predicted_length"] = merged["predicted_text"].str.len()
    merged["length_delta"] = merged["predicted_length"] - merged["true_length"]

    errors_only = merged.loc[~merged["exact_match"]].copy()
    errors_only.sort_values(by=["edit_distance", "confidence"], ascending=[False, True], inplace=True)

    summary = {
        "samples": int(len(merged)),
        "errors": int(len(errors_only)),
        "error_rate": float(len(errors_only) / len(merged)) if len(merged) else 0.0,
        "empty_predictions": int((merged["predicted_text"] == "").sum()),
        "low_confidence_predictions": int((merged["confidence"] < 0.3).sum()),
        "top_exact_mismatches": Counter(
            f"{row.true_text} -> {row.predicted_text or '[EMPTY]'}"
            for row in errors_only.itertuples(index=False)
        ).most_common(10),
        "confusion_pairs": [],
    }

    for left, right in CONFUSION_PAIRS:
        mask = errors_only["true_text"].str.contains(left, regex=False) & errors_only["predicted_text"].str.contains(right, regex=False)
        count = int(mask.sum())
        if count:
            summary["confusion_pairs"].append((f"{left}->{right}", count))

    return merged, errors_only, summary


def write_summary(summary_path: Path, summary: dict[str, object]) -> None:
    lines = [
        f"samples: {summary['samples']}",
        f"errors: {summary['errors']}",
        f"error_rate: {summary['error_rate']:.6f}",
        f"empty_predictions: {summary['empty_predictions']}",
        f"low_confidence_predictions: {summary['low_confidence_predictions']}",
        "",
        "top_exact_mismatches:",
    ]

    top_exact_mismatches = summary["top_exact_mismatches"]
    if top_exact_mismatches:
        for label, count in top_exact_mismatches:
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("confusion_pairs:")
    confusion_pairs = summary["confusion_pairs"]
    if confusion_pairs:
        for label, count in confusion_pairs:
            lines.append(f"- {label}: {count}")
    else:
        lines.append("- none")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build merged OCR error reports from truth and prediction CSV files.")
    parser.add_argument("truth_csv", type=Path)
    parser.add_argument("predictions_csv", type=Path)
    parser.add_argument("--merged-output", type=Path, required=True)
    parser.add_argument("--errors-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()

    merged, errors_only, summary = build_error_report(args.truth_csv, args.predictions_csv)
    args.merged_output.parent.mkdir(parents=True, exist_ok=True)
    args.errors_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)

    merged.to_csv(args.merged_output, index=False)
    errors_only.to_csv(args.errors_output, index=False)
    write_summary(args.summary_output, summary)

    print(f"Wrote merged report to {args.merged_output}")
    print(f"Wrote errors-only report to {args.errors_output}")
    print(f"Wrote summary to {args.summary_output}")


if __name__ == "__main__":
    main()
