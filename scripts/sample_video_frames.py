from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def sample_frames(video_path: Path, output_dir: Path, every_n_frames: int) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    saved = 0
    frame_index = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        if frame_index % every_n_frames == 0:
            output_path = output_dir / f"{video_path.stem}_frame_{frame_index:06d}.jpg"
            cv2.imwrite(str(output_path), frame)
            saved += 1

        frame_index += 1

    capture.release()
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample representative frames from a video.")
    parser.add_argument("video", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--every-n-frames", type=int, default=15)
    args = parser.parse_args()

    saved = sample_frames(args.video, args.output_dir, args.every_n_frames)
    print(f"Saved {saved} frames to {args.output_dir}")


if __name__ == "__main__":
    main()
