# Setup

## Requirements

This project is built for local Python execution with FastAPI.

Install dependencies with:

```bash
pip install -r requirements-local.txt
```

The detector and OCR engines depend on optional libraries:

- detector: `ultralytics`
- OCR: `paddleocr` preferred, `easyocr` as fallback

The app can still start if some of these are missing, but it will report non-ready component modes.

## Model Placement

Place the trained detector weights here:

```text
models/detector/best.pt
```

The app settings currently point to that path through `configs/app_settings.yaml`.

## Start the App

Preferred development command:

```bash
fastapi dev src/app.py
```

Fallback command:

```bash
uvicorn src.app:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Runtime Outputs

Important runtime paths:

- annotated output directory: `outputs/annotated_frames`
- crop output directory: `outputs/plate_crops`
- event log: `outputs/demo_logs/events.jsonl`

The current code creates these directories when needed. The live UI uses base64 image responses for display, while events are persisted to the JSONL log.

## Status and Fallback Behavior

The app exposes a status route at `GET /status`.

This is useful for checking whether:

- detector weights were found
- the detector loaded successfully
- OCR dependencies are available
- the camera is currently running

This project intentionally reports missing dependencies honestly instead of failing silently or pretending the system is ready.

## Recommended Sanity Checks

After setup:

1. Start the app.
2. Open the web UI.
3. Check the status panel or `GET /status`.
4. Upload a test image.
5. If using a webcam, test camera start and stop.

## Config Files

Main runtime settings live in:

- `configs/app_settings.yaml`
- `configs/plate_rules.yaml`

Main training dataset config:

- `configs/detector_data.yaml`

Prefer changing configuration in YAML rather than hardcoding values in Python modules.
