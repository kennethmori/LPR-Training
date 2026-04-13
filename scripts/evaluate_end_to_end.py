from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def evaluate(results_path: Path) -> dict[str, float]:
    df = pd.read_csv(results_path)
    required = {"detected", "true_text", "predicted_text", "pipeline_time_ms"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["true_text"] = df["true_text"].fillna("").astype(str)
    df["predicted_text"] = df["predicted_text"].fillna("").astype(str)
    df["exact_match"] = df["true_text"] == df["predicted_text"]
    df["detected"] = df["detected"].astype(bool)

    return {
        "samples": float(len(df)),
        "detection_rate": float(df["detected"].mean()),
        "end_to_end_exact_match_accuracy": float(df["exact_match"].mean()),
        "average_pipeline_time_ms": float(df["pipeline_time_ms"].mean()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate end-to-end detector plus OCR results.")
    parser.add_argument("results_csv", type=Path)
    args = parser.parse_args()

    metrics = evaluate(args.results_csv)
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
