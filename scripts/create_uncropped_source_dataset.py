from __future__ import annotations

import argparse
import csv
import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
CROP_SUFFIX_RE = re.compile(r"_(\d{2})$")


def source_stem_from_crop_path(crop_path: str) -> str:
    crop_file = Path(crop_path)
    stem = crop_file.stem
    return CROP_SUFFIX_RE.sub("", stem)


def build_source_index(images_root: Path) -> dict[str, dict[str, Path | str]]:
    index: dict[str, dict[str, Path | str]] = {}
    for split in ("train", "val", "test"):
        split_dir = images_root / split
        if not split_dir.exists():
            continue
        for image_path in split_dir.iterdir():
            if not image_path.is_file():
                continue
            index[image_path.stem] = {
                "path": image_path,
                "split": split,
            }
    return index


def curate_uncropped_sources(
    curated_labels_csv: Path,
    output_dir: Path,
    manifest_csv: Path,
    labels_output_csv: Path | None = None,
) -> dict[str, Any]:
    labels = pd.read_csv(curated_labels_csv)
    labels["image_path"] = labels["image_path"].fillna("").astype(str)
    labels["true_text"] = labels["true_text"].fillna("").astype(str)

    source_index = build_source_index(BASE_DIR / "data" / "images")
    labels_index: dict[tuple[str, str], Path] = {}
    for split in ("train", "val", "test"):
        label_dir = BASE_DIR / "data" / "labels" / split
        if not label_dir.exists():
            continue
        for label_path in label_dir.glob("*.txt"):
            labels_index[(split, label_path.stem)] = label_path

    images_dir = output_dir / "images"
    labels_dir = output_dir / "labels"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv.parent.mkdir(parents=True, exist_ok=True)
    if labels_output_csv is not None:
        labels_output_csv.parent.mkdir(parents=True, exist_ok=True)

    seen_sources: set[str] = set()
    manifest_rows: list[dict[str, str]] = []
    output_label_rows: list[dict[str, str]] = []

    for row in labels.itertuples(index=False):
        source_stem = source_stem_from_crop_path(row.image_path)
        source_info = source_index.get(source_stem)
        if source_info is None:
            continue

        source_path = Path(source_info["path"])
        split = str(source_info["split"])
        source_key = f"{split}:{source_stem}"

        dest_image_path = images_dir / source_path.name
        dest_label_path = labels_dir / f"{source_stem}.txt"

        if source_key not in seen_sources:
            shutil.copy2(source_path, dest_image_path)
            label_source = labels_index.get((split, source_stem))
            if label_source is not None and label_source.exists():
                shutil.copy2(label_source, dest_label_path)
            seen_sources.add(source_key)

        manifest_rows.append(
            {
                "split": split,
                "curated_crop_path": row.image_path,
                "source_image_path": str(source_path.relative_to(BASE_DIR).as_posix()),
                "source_label_path": str(dest_label_path.relative_to(BASE_DIR).as_posix()) if dest_label_path.exists() else "",
                "true_text": row.true_text,
            }
        )
        output_label_rows.append(
            {
                "curated_crop_path": row.image_path,
                "source_image_path": str(source_path.relative_to(BASE_DIR).as_posix()),
                "true_text": row.true_text,
            }
        )

    with manifest_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["split", "curated_crop_path", "source_image_path", "source_label_path", "true_text"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    if labels_output_csv is not None:
        with labels_output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["curated_crop_path", "source_image_path", "true_text"],
            )
            writer.writeheader()
            writer.writerows(output_label_rows)

    return {
        "unique_source_images": len(seen_sources),
        "crop_rows": len(manifest_rows),
        "output_dir": str(output_dir),
        "manifest_csv": str(manifest_csv),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trace curated crop datasets back to their uncropped source images.")
    parser.add_argument("curated_labels_csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-csv", type=Path, required=True)
    parser.add_argument("--labels-output-csv", type=Path, default=None)
    args = parser.parse_args()

    result = curate_uncropped_sources(
        curated_labels_csv=args.curated_labels_csv.resolve(),
        output_dir=args.output_dir.resolve(),
        manifest_csv=args.manifest_csv.resolve(),
        labels_output_csv=args.labels_output_csv.resolve() if args.labels_output_csv else None,
    )
    print(f"Unique source images: {result['unique_source_images']}")
    print(f"Curated crop rows: {result['crop_rows']}")
    print(f"Output dir: {result['output_dir']}")
    print(f"Manifest CSV: {result['manifest_csv']}")


if __name__ == "__main__":
    main()
