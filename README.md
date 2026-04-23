# USM License Plate Recognition Prototype

This repository contains a local-first University of Southern Mindanao license plate recognition system:

1. YOLO detects the license plate region.
2. OCR reads the cropped plate text.
3. Stable `entry` and `exit` reads are turned into vehicle-session events.

The current app already includes the recognition pipeline, a FastAPI dashboard, role-based camera handling, session tracking, and SQLite-backed persistence.

## Current App Capabilities

- one detector class: `plate_number`
- one primary plate result per frame
- image upload inference
- video upload inference
- live camera inference with role-aware `entry` and `exit` cameras
- pretrained OCR first
- conservative post-processing plus recent-history stabilization
- session tracking with cooldown and unmatched-exit handling
- FastAPI + Jinja2 web interface
- SQLite persistence for events and sessions
- JSONL debug logging and performance snapshots

## Project Layout

```text
configs/        App and dataset configuration
data/           Raw data, YOLO dataset, OCR crops, metadata manifests
docs/           Human-facing project documentation
models/         Trained detector weights and export artifacts
notebooks/      Colab and experiment notebook placeholders
scripts/        Data preparation and evaluation utilities
src/            Core pipeline, services, API routes, app entry point
templates/      HTML templates
static/         CSS, JS, and image assets
outputs/        Generated annotated frames, crops, logs, metrics, failures
```

## Current Dataset Status

The current workspace already contains prepared detector and OCR evaluation data.

YOLO detector dataset snapshot:

- `data/images/train` with `329` images and matching `329` label files
- `data/images/val` with `86` images and matching `86` label files
- `data/images/test` with `85` images and matching `85` label files
- `configs/detector_data.yaml` already points to `data/images/{train,val,test}`

OCR crop dataset snapshot:

- `data/ocr/train_crops` with `334` crops and `data/ocr/train_labels.csv`
- `data/ocr/val_crops` with `105` crops and `data/ocr/val_labels.csv`
- `data/ocr/test_crops` with `97` crops and `data/ocr/test_labels.csv`
- aggregated OCR evaluation set in `data/ocr/all_crops` with `data/ocr/all_labels.csv` for `536` total crops

Important note:

- some empty YOLO `.txt` files are intentional Roboflow null-image negatives and should not automatically be treated as missing annotations
- OCR labels were manually filled by visual inspection for evaluation use

## Documentation

For deeper project documentation, see:

- `docs/README.md`
- `docs/setup.md`
- `docs/architecture.md`
- `docs/CONTEXT.md`
- `docs/data-workflow.md`
- `docs/evaluation.md`
- `docs/implementation-roadmap.md`
- `docs/session-flow.md`
- `docs/missing-pieces.md`
- `docs/known-issues.md`

## Local Setup

Install the local runtime dependencies:

```bash
pip install -r requirements-local.txt
```

Start the web app:

```bash
fastapi dev src/app.py
```

If `fastapi dev` is unavailable in your environment, use:

```bash
uvicorn src.app:app --reload
```

Open `http://127.0.0.1:8000`.

## Detector Runtime

The current default detector backend is `onnxruntime`, configured through `configs/app_settings.yaml`.

- default ONNX path: `models/detector/yolo26nbest.onnx`
- Ultralytics fallback weights path: `models/detector/yolo26nbest.pt`

If you switch `detector.backend` back to `ultralytics`, make sure `models/detector/yolo26nbest.pt` exists.

## Main Runtime Outputs

- SQLite database: `outputs/app_data/plate_events.db`
- uploaded videos: `outputs/app_data/video_uploads`
- event log: `outputs/demo_logs/events.jsonl`
- performance log: `outputs/demo_logs/performance.jsonl`
- annotated frames: `outputs/annotated_frames`
- plate crops: `outputs/plate_crops`

## Automated Checks

Run these checks before shipping changes:

```bash
python -m compileall src scripts
python -m unittest discover -s tests -p "test_*.py"
```

## Recommended Next Priorities

1. Expand automated coverage for long-running camera loops, video-upload paths, and end-to-end role-based flows.
2. Tighten schema-first API response handling for routes that still return ad hoc payload shapes.
3. Add database migration or versioning support.
4. Improve moderation and operator-facing runbooks for real deployments.
5. Continue detector and OCR quality improvements for difficult plate cases.

## Notes

- Detection labels alone are not enough to claim recognition performance.
- OCR evaluation requires cropped plate images with true text labels.
- The current OCR setup supports evaluation directly from the prepared crop folders and CSV truth files even without training a custom OCR recognizer.
- Run aggregated OCR evaluation with:

```bash
python scripts/run_ocr_evaluation.py data/ocr/all_crops data/ocr/all_labels.csv
```

- The runtime is local-first: recognition and session logging should continue working without internet access.
- JSONL logs are useful for debugging, but SQLite is the durable operational store.
