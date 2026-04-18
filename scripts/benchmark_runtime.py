from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _iter_image_paths(image: Path | None, image_dir: Path | None) -> list[Path]:
    paths: list[Path] = []
    if image is not None:
        paths.append(image)
    if image_dir is not None:
        paths.extend(sorted(path for path in image_dir.iterdir() if path.is_file()))
    return paths


def _safe_average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _collect_summary(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    stable_plates: list[str] = []
    for payload in payloads:
        stable = payload.get("stable_result") or {}
        value = str(stable.get("value") or "").strip()
        if stable.get("accepted") and value and value not in stable_plates:
            stable_plates.append(value)

    detector_timings = [float((payload.get("timings_ms") or {}).get("detector") or 0.0) for payload in payloads]
    ocr_timings = [float((payload.get("timings_ms") or {}).get("ocr") or 0.0) for payload in payloads]
    pipeline_timings = [float((payload.get("timings_ms") or {}).get("pipeline") or 0.0) for payload in payloads]

    return {
        "frames_processed": len(payloads),
        "frames_with_detection": sum(1 for payload in payloads if payload.get("plate_detected")),
        "frames_with_accepted_stable_result": sum(
            1 for payload in payloads if (payload.get("stable_result") or {}).get("accepted")
        ),
        "avg_detector_ms": _safe_average(detector_timings),
        "avg_ocr_ms": _safe_average(ocr_timings),
        "avg_pipeline_ms": _safe_average(pipeline_timings),
        "stable_plates": stable_plates,
    }


def benchmark_images(image: Path | None, image_dir: Path | None) -> dict[str, Any]:
    from src.app import create_app

    image_paths = _iter_image_paths(image, image_dir)
    if not image_paths:
        raise SystemExit("No images found. Provide --image or --image-dir.")

    app = create_app()
    pipeline = app.state.pipeline
    pipeline.settings["save_event_images"] = False
    payloads: list[dict[str, Any]] = []

    for image_path in image_paths:
        frame = cv2.imread(str(image_path))
        if frame is None:
            continue
        payload, _, _ = pipeline.process_frame(
            frame,
            source_type="benchmark",
            camera_role="benchmark",
            source_name=image_path.name,
            stream_key=f"benchmark:image:{image_path.name}",
        )
        payloads.append(payload)

    return {
        "mode": "images",
        "inputs": [str(path) for path in image_paths],
        **_collect_summary(payloads),
    }


def benchmark_video(video: Path, every_n_frames: int, max_frames: int) -> dict[str, Any]:
    from src.app import create_app

    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Unable to open video: {video}")

    app = create_app()
    pipeline = app.state.pipeline
    pipeline.settings["save_event_images"] = False
    payloads: list[dict[str, Any]] = []
    processed = 0
    frame_index = -1
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)

    try:
        while processed < max_frames:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % every_n_frames != 0:
                continue

            payload, _, _ = pipeline.process_frame(
                frame,
                source_type="benchmark_video",
                camera_role="benchmark",
                source_name=video.name,
                stream_key=f"benchmark:video:{video.name}",
            )
            payload["frame_index"] = frame_index
            payloads.append(payload)
            processed += 1
    finally:
        capture.release()

    return {
        "mode": "video",
        "input": str(video),
        "fps": round(fps, 3),
        "sample_every_n_frames": every_n_frames,
        "max_frames": max_frames,
        **_collect_summary(payloads),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark detector/OCR runtime on sample images or video.")
    parser.add_argument("--image", type=Path, help="Single image to process.")
    parser.add_argument("--image-dir", type=Path, help="Directory of images to process.")
    parser.add_argument("--video", type=Path, help="Video to sample and process.")
    parser.add_argument("--every-n-frames", type=int, default=3, help="Sample interval for video benchmarking.")
    parser.add_argument("--max-frames", type=int, default=300, help="Maximum sampled video frames to process.")
    parser.add_argument("--output-json", type=Path, help="Optional path for saving the summary JSON.")
    args = parser.parse_args()

    if args.video is None and args.image is None and args.image_dir is None:
        raise SystemExit("Provide --video, --image, or --image-dir.")

    if args.video is not None:
        summary = benchmark_video(
            video=args.video,
            every_n_frames=max(int(args.every_n_frames), 1),
            max_frames=max(int(args.max_frames), 1),
        )
    else:
        summary = benchmark_images(args.image, args.image_dir)

    output = json.dumps(summary, indent=2)
    print(output)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(output + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
