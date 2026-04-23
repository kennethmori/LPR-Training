# Setup

## Requirements

This project is built for local Python execution with FastAPI.

Install dependencies with:

```bash
pip install -r requirements-local.txt
```

For Windows laptops that should try the iGPU through ONNX Runtime DirectML, use the DirectML-specific environment instead:

```bash
pip install -r requirements-local-directml.txt
```

Optional runtime dependencies depend on which detector and OCR backends you want to use:

- detector runtime, default path: `onnxruntime`
- detector training and PT runtime: `ultralytics`
- OCR: `paddleocr` preferred, `easyocr` as fallback

The app can still start if some of these are missing, but it will report non-ready component modes instead of pretending everything is available.

## Detector Model Paths

The current config defaults to an ONNX detector runtime.

Current default detector settings in `configs/app_settings.yaml`:

- `detector.backend: onnxruntime`
- `detector.onnx_weights_path: models/detector/yolo26nbest.onnx`
- `detector.onnx_execution_providers: [DmlExecutionProvider, CPUExecutionProvider]`

That provider order lets a Windows DirectML install try the AMD/Intel/NVIDIA GPU first while still falling back to CPU when DirectML is unavailable or cannot create the session.

Ultralytics weights are still supported when you switch the backend:

- `paths.detector_weights: models/detector/yolo26nbest.pt`

If the detector does not load, verify that the configured backend matches the model file you actually have.

## Start The App

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

## Automated Validation

Run these commands before or after manual sanity checks:

```bash
python -m compileall src scripts
python -m unittest discover -s tests -p "test_*.py"
```

## Runtime Outputs

Important runtime paths:

- SQLite database: `outputs/app_data/plate_events.db`
- uploaded videos: `outputs/app_data/video_uploads`
- annotated output directory: `outputs/annotated_frames`
- crop output directory: `outputs/plate_crops`
- event log: `outputs/demo_logs/events.jsonl`
- performance log: `outputs/demo_logs/performance.jsonl`

The current code creates these directories when needed. SQLite is the operational source of truth for sessions and recent events, while JSONL logs remain useful for debugging.

## Status And Fallback Behavior

The app exposes a status route at `GET /status`.

This is useful for checking whether:

- detector weights and backend are ready
- the active ONNX execution provider list includes `DmlExecutionProvider`
- OCR dependencies are available
- SQLite storage initialized successfully
- the session layer is ready
- one or more camera roles are currently running

This project intentionally reports missing dependencies honestly instead of failing silently or pretending the system is ready.

## Recommended Sanity Checks

After setup:

1. Start the app.
2. Open the web UI.
3. Check the status panel or `GET /status`.
4. Upload a test image through `/predict/image`.
5. Upload a short test video through `/predict/video`.
6. Start and stop the configured `entry` camera.
7. If an `exit` camera source is configured, test that role too.
8. Check `/sessions/active`, `/events/recent`, and `/performance/summary` after a few runs.

## Config Files

Main runtime settings live in:

- `configs/app_settings.yaml`
- `configs/plate_rules.yaml`

Important sections in `configs/app_settings.yaml` include:

- `paths`
- `detector`
- `ocr`
- `postprocess`
- `stabilization`
- `tracking`
- `session`
- `cameras`
- `uploads`

Main training dataset config:

- `configs/detector_data.yaml`

Prefer changing configuration in YAML rather than hardcoding values in Python modules.
