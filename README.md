# USM License Plate Recognition Prototype

This repository is a starter for a two-stage University of Southern Mindanao license plate recognition system:

1. YOLO detects the license plate region.
2. OCR reads the cropped plate text.

The scaffold is designed for the workflow recommended in your project blueprint:

- fine-tune the detector in Google Colab
- run the final prototype locally
- keep detection, OCR, post-processing, and UI clearly separated
- report detector-only, OCR-only, and end-to-end results independently

## Version 1 Scope

- one detector class: `plate_number`
- one primary plate result per frame
- image upload plus live webcam
- pretrained OCR first
- FastAPI + Jinja2 web interface
- conservative post-processing only

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

## Recommended Build Order

1. Prepare data and manifests.
2. Fine-tune `yolo26s.pt` in Colab.
3. Place `best.pt` in `models/detector/`.
4. Build and validate still-image inference locally.
5. Add saved-video inference.
6. Add webcam mode.
7. Finalize UI polish and evaluation outputs.

## Current Dataset Status

The current workspace already contains prepared detector and OCR evaluation data.

YOLO detector dataset snapshot:

- `data/images/train` with `329` images and matching `329` label files
- `data/images/val` with `86` images and matching `86` label files
- `data/images/test` with `85` images and matching `85` label files
- `configs/detector_data.yaml` already points to `data/images/{train,val,test}`

OCR crop dataset snapshot:

- `data/ocr/train_crops` with `334` crops and [train_labels.csv](C:\4 BSCS\4 bscs 2nd sem\IntelligentSystems\plate\data\ocr\train_labels.csv)
- `data/ocr/val_crops` with `105` crops and [val_labels.csv](C:\4 BSCS\4 bscs 2nd sem\IntelligentSystems\plate\data\ocr\val_labels.csv)
- `data/ocr/test_crops` with `97` crops and [test_labels.csv](C:\4 BSCS\4 bscs 2nd sem\IntelligentSystems\plate\data\ocr\test_labels.csv)
- aggregated OCR evaluation set in [all_crops](C:\4 BSCS\4 bscs 2nd sem\IntelligentSystems\plate\data\ocr\all_crops) with [all_labels.csv](C:\4 BSCS\4 bscs 2nd sem\IntelligentSystems\plate\data\ocr\all_labels.csv) for `536` total crops

Important note:

- some empty YOLO `.txt` files are intentional Roboflow null-image negatives and should not automatically be treated as missing annotations
- OCR labels were manually filled by visual inspection for evaluation use

## Documentation

For deeper project documentation, see:

- `docs/README.md`
- `docs/setup.md`
- `docs/architecture.md`
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

## Model Placement

Put your trained detector weights here:

```text
models/detector/best.pt
```

The app will start even if the detector or OCR dependencies are missing, but the status endpoint and UI will show which modules are unavailable so the prototype stays honest.

## Recommended Detector Baseline

Use `yolo26s.pt` as the main detector baseline.

- main choice: `yolo26s.pt`
- fallback for weaker hardware: `yolo26n.pt`

You can train with the helper script:

```bash
python scripts/train_detector.py --data configs/detector_data.yaml --model yolo26s.pt
```

## Notes

- Detection labels alone are not enough to claim recognition performance.
- OCR evaluation requires cropped plate images with true text labels.
- The current OCR setup supports evaluation directly from the prepared crop folders and CSV truth files even without training a custom OCR recognizer.
- Avoid random image-only splitting when the same plate appears across nearby frames.
- Treat Colab runtime metrics and local CPU runtime metrics as separate results.
