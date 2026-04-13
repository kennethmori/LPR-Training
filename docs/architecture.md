# Architecture

## Overview

This project is a two-stage license plate recognition system:

1. A YOLO detector finds the plate region.
2. An OCR engine reads text from the cropped plate.
3. A post-processing and stabilization layer cleans the text and decides what result to show.

The live application is served through FastAPI with a simple Jinja2 and vanilla JavaScript frontend.

At the moment, the runtime architecture covers recognition only. The planned campus deployment adds an entry and exit session layer on top of recognition events. That future direction is documented in [session-flow.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/session-flow.md).

## Main Runtime Flow

The application starts in `src/app.py`.

At startup it:

- loads settings from `configs/app_settings.yaml`
- creates the detector, OCR engine, post-processor, result stabilizer, logger, pipeline, and camera service
- stores these objects in `app.state`
- registers the API routes and serves the frontend

The current startup flow creates a single camera service. A future entry/exit deployment will likely replace this with two camera instances or a higher-level manager that understands camera roles.

## Core Components

### `src/core/detector.py`

`PlateDetector` loads `models/detector/best.pt` through Ultralytics YOLO.

Responsibilities:

- check whether detector weights exist
- load the YOLO model if dependencies are available
- run detection on an image
- return detections sorted by confidence

If weights are missing or Ultralytics is unavailable, the detector reports an honest mode such as `missing_weights` or `ultralytics_not_installed`.

### `src/core/cropper.py`

Cropping helpers handle:

- bounding-box padding
- plate crop extraction
- crop resizing for OCR
- drawing annotations on the output frame

The current pipeline keeps only the highest-confidence detection for final OCR.

### `src/core/ocr_engine.py`

`PlateOCREngine` tries OCR engines in this order:

1. `PaddleOCR`
2. `EasyOCR`

Responsibilities:

- load the first available OCR engine
- run OCR on the cropped image
- normalize the OCR response into a consistent payload

If OCR dependencies are missing, the engine stays in a non-ready mode rather than crashing the app.

### `src/core/postprocess.py`

`PlateTextPostProcessor` applies conservative cleanup:

- uppercase conversion
- whitespace collapse
- non-alphanumeric stripping
- optional soft substitution rules from `configs/plate_rules.yaml`

This keeps the current project aligned with a cautious prototype workflow.

### `src/services/result_service.py`

`ResultService` stabilizes recognition results across recent frames.

It stores a short history of OCR outputs and promotes the most frequent value once it appears often enough. This is especially important for webcam mode where OCR can flicker frame to frame.

This stabilizer is not the same thing as session tracking. It only makes the recognized text more reliable before another layer decides whether that text should open or close a visit session.

### `src/services/logging_service.py`

`LoggingService` appends JSON lines to `outputs/demo_logs/events.jsonl`.

Each record captures:

- timestamp
- source type
- whether a plate was detected
- detector and OCR confidence
- raw, cleaned, and stable text
- timing information

### `src/services/camera_service.py`

`CameraService` manages webcam capture on a background thread.

Responsibilities:

- start and stop the webcam
- process every Nth frame through the pipeline
- keep the latest inference payload
- expose an MJPEG stream for the frontend

The current implementation assumes one live camera source. Entry and exit handling will require role-aware camera management.

## End-to-End Pipeline

The main inference logic lives in `src/core/pipeline.py`.

For each frame:

1. run detector inference
2. if no detections exist, return a `no_detection` payload
3. crop the best plate region
4. resize the crop for OCR
5. run OCR
6. clean the OCR text
7. update the stabilized result
8. annotate the frame
9. log the event
10. return payload plus image outputs

For image uploads, the API also base64-encodes the annotated image and crop so the browser can display them immediately.

In the planned campus deployment, this pipeline should emit stable recognition events that a separate session layer can consume.

## Planned Session Layer

The intended next architectural layer is session tracking for campus entry and exit.

Target behavior:

- an `entry` camera opens a session for a recognized plate
- an `exit` camera closes the matching open session
- duplicate events from repeated frames are filtered through cooldown and debouncing rules

This should be implemented above the recognition pipeline rather than inside detector or OCR code.

## API Layer

Routes are defined in `src/api/routes.py`.

Current endpoints:

- `GET /`: render the main web UI
- `POST /predict/image`: run inference on an uploaded image
- `POST /camera/start`: start webcam capture
- `POST /camera/stop`: stop webcam capture
- `GET /stream`: return the MJPEG camera stream
- `GET /latest-result`: return the latest inference payload
- `GET /status`: report detector, OCR, and camera readiness

`src/api/schemas.py` defines Pydantic payload models, but current route handlers mostly return plain dictionaries.

## Frontend

The frontend is intentionally simple:

- `templates/index.html` defines the page structure
- `static/js/app.js` handles uploads, camera controls, and status refreshes
- `static/css/style.css` provides the visual styling

The UI is a dashboard rather than a large frontend app. That keeps iteration fast for a thesis or prototype setting.
