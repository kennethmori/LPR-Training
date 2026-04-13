# Repository Guidelines

## Project Structure & Module Organization

This repository is a two-stage license plate recognition project: YOLO detects `plate_number`, then OCR reads cropped plate text.

- `src/` contains the app code.
- `src/app.py` is the FastAPI entry point and wires settings, detector, OCR, post-processing, pipeline, logging, and camera services.
- `src/core/` holds detector, cropper, OCR, post-processing, and pipeline logic.
- `src/services/` contains camera, logging, result stabilization, and future session-tracking services.
- `src/api/` defines FastAPI routes and schemas. Schemas currently document payload shapes; most routes still return plain dict responses.
- `templates/` and `static/` contain the web UI.
- `configs/` stores dataset and app YAML files.
- `scripts/` contains data preparation, crop export, evaluation, and training helpers.
- `data/` stores raw media, YOLO datasets, OCR crops, and metadata manifests.
- `outputs/` is for generated artifacts only.

## Current Dataset Snapshot

The current workspace already includes prepared detector and OCR evaluation assets.

- detector data currently uses `data/images/{train,val,test}` and `data/labels/{train,val,test}`
- current YOLO split counts are `329` train images, `86` val images, and `85` test images, each with matching label file counts
- OCR truth currently uses `data/ocr/train_crops`, `data/ocr/val_crops`, and `data/ocr/test_crops` with matching CSV labels
- current OCR crop counts are `334` train, `105` val, and `97` test
- an aggregated OCR evaluation set also exists at `data/ocr/all_crops` with `data/ocr/all_labels.csv` for `536` total crops

Keep these counts and paths in mind before changing scripts or documentation, since they reflect the current checked workspace rather than an abstract target layout.

## Runtime Behavior

- The app expects detector weights at `models/detector/best.pt`.
- Runtime events are appended to `outputs/demo_logs/events.jsonl`.
- The pipeline returns one primary plate result per frame and uses recent-history stabilization for camera mode.
- The app is designed to degrade gracefully when detector weights or OCR dependencies are missing; status endpoints and the UI should report the active mode honestly instead of pretending modules are ready.
- The current live app recognizes plates from a single camera source. Entry and exit session management is a planned extension and should be implemented as a separate layer on top of plate-recognition events.

## Build, Test, and Development Commands

- `pip install -r requirements-local.txt` installs the local runtime dependencies.
- `fastapi dev src/app.py` starts the web app in development mode.
- `uvicorn src.app:app --reload` is the fallback local server command.
- `python scripts/train_detector.py --data configs/detector_data.yaml --model yolo26s.pt` fine-tunes the detector.
- `python -m compileall src scripts` performs a quick syntax check.

## Coding Style & Naming Conventions

- Use 4-space indentation and standard Python typing where practical.
- Prefer short, focused modules over large mixed-purpose files.
- Use `snake_case` for Python files, functions, variables, and CSV/YAML fields.
- Keep detector class naming consistent with the dataset: `plate_number`.
- Preserve raw data; write derived files to `data/interim/`, `data/ocr/`, or `outputs/`.

## Testing Guidelines

No formal test suite is configured yet. Until one is added:

- run `python -m compileall src scripts` before submitting changes
- test the relevant workflow locally, such as image upload or crop generation
- verify `/status`, image upload inference, and camera start/stop behavior when touching runtime code
- keep sample outputs and temporary experiments out of committed source folders

If tests are added later, place them in a top-level `tests/` directory and use `test_*.py` naming.

## Current Constraints

- Current scope is centered on a single detector class: `plate_number`.
- The live pipeline selects the highest-confidence detection rather than handling multiple final plate reads per frame.
- OCR uses pretrained engines first (`PaddleOCR`, then `EasyOCR` fallback) rather than a custom recognizer.
- The current OCR dataset is prepared primarily for evaluation of pretrained OCR output; custom OCR training is optional future work rather than a current requirement.
- Config changes should be made in `configs/app_settings.yaml` or other YAML files instead of hardcoding values in the app.
- Entry and exit session tracking is not implemented yet. When adding it, keep recognition logic separate from session lifecycle logic.

## Data Handling Notes

- Empty YOLO label files are not automatically errors in this repo. Some come from Roboflow null-image negatives and are intentional.
- Before treating an empty detector label file as a missing annotation, check whether the source image belongs to that null-image set.
- OCR `true_text` values should be based on manual visual inspection of the crop when ground truth is being curated.
- Do not destroy or reshuffle the existing OCR crop split folders unless the task explicitly calls for a new split strategy.

## Planned Entry/Exit Direction

- The target deployment model is two live cameras: one `entry` camera and one `exit` camera.
- Stable plate reads from the `entry` camera should open a vehicle session.
- Stable plate reads from the `exit` camera should close the most recent open session for the same plate.
- Add debouncing or cooldown rules so repeated detections from the same car do not create duplicate entry or exit events.
- Prefer a dedicated session service and durable storage such as SQLite rather than embedding session state directly inside camera or OCR code.

## Commit & Pull Request Guidelines

There is no meaningful Git history in this workspace yet, so use simple imperative commit messages, for example:

- `Add YOLO26 training helper`
- `Align detector class name with Roboflow export`

Pull requests should include:

- a short summary of what changed
- any config or dataset assumptions
- commands used for verification
- screenshots for UI changes when applicable

## Security & Data Handling

Treat plate images as sensitive project data. Keep originals in `data/raw/`, avoid destructive edits, and do not publish private sample media or generated labels without approval.
