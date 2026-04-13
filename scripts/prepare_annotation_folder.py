from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def prepare_annotation_folder(raw_dir: Path, output_dir: Path, manifest_path: Path, prefix: str) -> int:
    raw_dir = raw_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    image_paths = [
        path for path in sorted(raw_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "original_name",
                "original_path",
                "clean_name",
                "clean_path",
                "extension",
                "size_bytes",
                "annotation_status",
                "true_text",
                "notes",
            ],
        )
        writer.writeheader()

        for index, source_path in enumerate(image_paths, start=1):
            extension = source_path.suffix.lower()
            clean_name = f"{prefix}_{index:06d}{extension}"
            clean_path = output_dir / clean_name
            shutil.copy2(source_path, clean_path)

            writer.writerow(
                {
                    "index": index,
                    "original_name": source_path.name,
                    "original_path": str(source_path),
                    "clean_name": clean_name,
                    "clean_path": str(clean_path),
                    "extension": extension,
                    "size_bytes": source_path.stat().st_size,
                    "annotation_status": "pending",
                    "true_text": "",
                    "notes": "",
                }
            )

    return len(image_paths)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a clean, annotation-ready image folder and manifest.")
    parser.add_argument("raw_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("manifest_path", type=Path)
    parser.add_argument("--prefix", default="usm_img")
    args = parser.parse_args()

    count = prepare_annotation_folder(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        manifest_path=args.manifest_path,
        prefix=args.prefix,
    )
    print(f"Prepared {count} images in {args.output_dir}")
    print(f"Manifest written to {args.manifest_path}")


if __name__ == "__main__":
    main()
