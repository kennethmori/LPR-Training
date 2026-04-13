from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a license plate detector with Ultralytics YOLO.")
    parser.add_argument("--data", default="configs/detector_data.yaml", help="Path to dataset YAML.")
    parser.add_argument("--model", default="yolo26s.pt", help="Pretrained model checkpoint to fine-tune.")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--project", default="runs/usm_lpr")
    parser.add_argument("--name", default="yolo26s_plate")
    parser.add_argument("--patience", type=int, default=20)
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(
        data=str(Path(args.data)),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
        patience=args.patience,
    )


if __name__ == "__main__":
    main()
