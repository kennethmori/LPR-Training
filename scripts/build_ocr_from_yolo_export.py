from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yaml
from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_class_names(dataset_root: Path) -> dict[int, str]:
    data_yaml = dataset_root / "data.yaml"
    if not data_yaml.exists():
        return {}

    with data_yaml.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    names = payload.get("names", {})
    if isinstance(names, list):
        return {index: str(name) for index, name in enumerate(names)}
    if isinstance(names, dict):
        return {int(index): str(name) for index, name in names.items()}
    return {}


def iter_split_dirs(dataset_root: Path) -> list[tuple[str, Path, Path]]:
    candidates = []
    for split_name in ("train", "valid", "val", "test"):
        split_dir = dataset_root / split_name
        image_dir = split_dir / "images"
        label_dir = split_dir / "labels"
        if image_dir.exists() and label_dir.exists():
            normalized = "val" if split_name == "valid" else split_name
            candidates.append((normalized, image_dir, label_dir))
    return candidates


def yolo_to_xyxy(x_center: float, y_center: float, width: float, height: float, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    x1 = int((x_center - width / 2) * image_width)
    y1 = int((y_center - height / 2) * image_height)
    x2 = int((x_center + width / 2) * image_width)
    y2 = int((y_center + height / 2) * image_height)
    return x1, y1, x2, y2


def build_ocr_dataset(dataset_root: Path, output_root: Path, manifest_path: Path, padding_ratio: float) -> int:
    class_names = load_class_names(dataset_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    total_crops = 0

    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "split",
                "source_image",
                "label_file",
                "crop_path",
                "class_id",
                "class_name",
                "bbox_x1",
                "bbox_y1",
                "bbox_x2",
                "bbox_y2",
                "true_text",
                "ocr_guess",
                "notes",
            ],
        )
        writer.writeheader()

        for split_name, image_dir, label_dir in iter_split_dirs(dataset_root):
            split_output_dir = output_root / split_name
            split_output_dir.mkdir(parents=True, exist_ok=True)

            for image_path in sorted(image_dir.iterdir()):
                if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue

                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.exists():
                    continue

                try:
                    image = Image.open(image_path).convert("RGB")
                except OSError:
                    continue

                image_width, image_height = image.size

                with label_path.open("r", encoding="utf-8") as label_handle:
                    for crop_index, line in enumerate(label_handle):
                        parts = line.strip().split()
                        if len(parts) != 5:
                            continue

                        class_id = int(float(parts[0]))
                        x_center, y_center, width, height = map(float, parts[1:])
                        x1, y1, x2, y2 = yolo_to_xyxy(x_center, y_center, width, height, image_width, image_height)

                        pad_x = int((x2 - x1) * padding_ratio)
                        pad_y = int((y2 - y1) * padding_ratio)
                        x1 = max(0, x1 - pad_x)
                        y1 = max(0, y1 - pad_y)
                        x2 = min(image_width, x2 + pad_x)
                        y2 = min(image_height, y2 + pad_y)

                        if x2 <= x1 or y2 <= y1:
                            continue

                        crop_name = f"{image_path.stem}_{crop_index:02d}.jpg"
                        crop_path = split_output_dir / crop_name
                        crop = image.crop((x1, y1, x2, y2))
                        crop.save(crop_path, format="JPEG", quality=95)

                        writer.writerow(
                            {
                                "split": split_name,
                                "source_image": str(image_path),
                                "label_file": str(label_path),
                                "crop_path": str(crop_path),
                                "class_id": class_id,
                                "class_name": class_names.get(class_id, f"class_{class_id}"),
                                "bbox_x1": x1,
                                "bbox_y1": y1,
                                "bbox_x2": x2,
                                "bbox_y2": y2,
                                "true_text": "",
                                "ocr_guess": "",
                                "notes": "",
                            }
                        )
                        total_crops += 1

    return total_crops


def main() -> None:
    parser = argparse.ArgumentParser(description="Create OCR crops and a manifest from a YOLO export.")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("manifest_path", type=Path)
    parser.add_argument("--padding-ratio", type=float, default=0.05)
    args = parser.parse_args()

    total_crops = build_ocr_dataset(
        dataset_root=args.dataset_root,
        output_root=args.output_root,
        manifest_path=args.manifest_path,
        padding_ratio=args.padding_ratio,
    )
    print(f"Created {total_crops} OCR crops.")
    print(f"Manifest written to {args.manifest_path}")


if __name__ == "__main__":
    main()
