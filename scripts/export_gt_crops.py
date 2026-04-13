from __future__ import annotations

import argparse
from pathlib import Path

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency fallback
    cv2 = None

from PIL import Image


def yolo_to_xyxy(x_center: float, y_center: float, width: float, height: float, image_width: int, image_height: int) -> tuple[int, int, int, int]:
    x1 = int((x_center - width / 2) * image_width)
    y1 = int((y_center - height / 2) * image_height)
    x2 = int((x_center + width / 2) * image_width)
    y2 = int((y_center + height / 2) * image_height)
    return x1, y1, x2, y2


def export_crops(images_dir: Path, labels_dir: Path, output_dir: Path, padding_ratio: float) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = 0

    for image_path in images_dir.glob("*.*"):
        label_path = labels_dir / f"{image_path.stem}.txt"
        if not label_path.exists():
            continue

        if cv2 is not None:
            image = cv2.imread(str(image_path))
            if image is None:
                continue
            image_height, image_width = image.shape[:2]
        else:
            try:
                image = Image.open(image_path).convert("RGB")
            except Exception:
                continue
            image_width, image_height = image.size

        with label_path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle):
                parts = line.strip().split()
                if len(parts) != 5:
                    continue

                _, x_center, y_center, width, height = map(float, parts)
                x1, y1, x2, y2 = yolo_to_xyxy(x_center, y_center, width, height, image_width, image_height)

                pad_x = int((x2 - x1) * padding_ratio)
                pad_y = int((y2 - y1) * padding_ratio)

                x1 = max(0, x1 - pad_x)
                y1 = max(0, y1 - pad_y)
                x2 = min(image_width, x2 + pad_x)
                y2 = min(image_height, y2 + pad_y)

                output_path = output_dir / f"{image_path.stem}_{idx:02d}.jpg"
                if cv2 is not None:
                    crop = image[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    cv2.imwrite(str(output_path), crop)
                else:
                    if x2 <= x1 or y2 <= y1:
                        continue
                    crop = image.crop((x1, y1, x2, y2))
                    if crop.size[0] == 0 or crop.size[1] == 0:
                        continue
                    crop.save(output_path, format="JPEG", quality=95)
                exported += 1

    return exported


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OCR ground-truth crops from YOLO labels.")
    parser.add_argument("images_dir", type=Path)
    parser.add_argument("labels_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--padding-ratio", type=float, default=0.05)
    args = parser.parse_args()

    exported = export_crops(args.images_dir, args.labels_dir, args.output_dir, args.padding_ratio)
    print(f"Exported {exported} crops to {args.output_dir}")


if __name__ == "__main__":
    main()
