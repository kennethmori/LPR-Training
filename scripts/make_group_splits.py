from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def assign_group_splits(
    manifest_path: Path,
    output_path: Path,
    group_column: str,
    train_ratio: float,
    val_ratio: float,
) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path)
    if group_column not in manifest.columns:
        raise ValueError(f"Missing group column: {group_column}")

    groups = manifest[group_column].dropna().astype(str).unique().tolist()
    groups.sort()

    train_cut = int(len(groups) * train_ratio)
    val_cut = train_cut + int(len(groups) * val_ratio)

    assignments = []
    for index, group_id in enumerate(groups):
        if index < train_cut:
            split = "train"
        elif index < val_cut:
            split = "val"
        else:
            split = "test"
        assignments.append(
            {
                "group_id": group_id,
                "group_type": group_column,
                "assigned_split": split,
            }
        )

    df = pd.DataFrame(assignments)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Create simple group-based train/val/test split assignments.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--group-column", default="plate_id")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args()

    df = assign_group_splits(
        manifest_path=args.manifest,
        output_path=args.output,
        group_column=args.group_column,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    print(df.head())


if __name__ == "__main__":
    main()
