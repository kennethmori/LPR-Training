from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insert_cost = curr[j - 1] + 1
            delete_cost = prev[j] + 1
            replace_cost = prev[j - 1] + (ca != cb)
            curr.append(min(insert_cost, delete_cost, replace_cost))
        prev = curr
    return prev[-1]


def evaluate(truth_path: Path, predictions_path: Path) -> dict[str, float]:
    truth = pd.read_csv(truth_path)
    predictions = pd.read_csv(predictions_path)
    merged = truth.merge(predictions, on="image_path", how="inner")
    if merged.empty:
        raise ValueError("No overlapping image_path values between truth and predictions.")

    merged["true_text"] = merged["true_text"].fillna("").astype(str)
    merged["predicted_text"] = merged["predicted_text"].fillna("").astype(str)
    merged["edit_distance"] = merged.apply(lambda row: levenshtein_distance(row["true_text"], row["predicted_text"]), axis=1)
    merged["exact_match"] = merged["true_text"] == merged["predicted_text"]

    total_chars = merged["true_text"].str.len().sum()
    total_edits = merged["edit_distance"].sum()

    return {
        "samples": float(len(merged)),
        "exact_match_accuracy": float(merged["exact_match"].mean()),
        "character_accuracy": float(1 - (total_edits / total_chars)) if total_chars else 0.0,
        "average_edit_distance": float(merged["edit_distance"].mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate OCR predictions against ground truth labels.")
    parser.add_argument("truth_csv", type=Path)
    parser.add_argument("predictions_csv", type=Path)
    args = parser.parse_args()

    metrics = evaluate(args.truth_csv, args.predictions_csv)
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
