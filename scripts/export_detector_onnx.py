from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the trained detector to ONNX for ONNX Runtime.")
    parser.add_argument("--weights", default="models/detector/best.pt", help="Path to the trained .pt detector.")
    parser.add_argument("--imgsz", type=int, default=640, help="Export image size.")
    parser.add_argument("--opset", type=int, default=12, help="ONNX opset version.")
    parser.add_argument(
        "--output",
        default="outputs/detector/best.onnx",
        help="Final ONNX output path.",
    )
    parser.add_argument("--simplify", action="store_true", help="Simplify the exported ONNX graph when supported.")
    args = parser.parse_args()

    weights_path = Path(args.weights).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=str(output_path.parent)) as temp_dir:
        temp_dir_path = Path(temp_dir)
        staged_weights_path = temp_dir_path / weights_path.name
        shutil.copy2(weights_path, staged_weights_path)

        model = YOLO(str(staged_weights_path))
        exported_path = model.export(
            format="onnx",
            imgsz=args.imgsz,
            opset=args.opset,
            simplify=args.simplify,
        )

        exported = Path(str(exported_path)).resolve()
        shutil.copy2(exported, output_path)

    print(f"ONNX detector ready at: {output_path}")


if __name__ == "__main__":
    main()
