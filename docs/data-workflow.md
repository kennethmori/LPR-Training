# Data Workflow

## Overview

This repository separates raw media, prepared annotation data, OCR assets, and generated outputs.

Important directories:

- `data/raw/`: original source images and videos
- `data/interim/`: cleaned or prepared intermediate assets
- `data/metadata/`: manifests, split files, and annotation tracking CSVs
- `data/images/` and `data/labels/`: YOLO detector training, validation, and test layout
- `data/ocr/`: OCR-related labels, crop datasets, and aggregated evaluation assets
- `outputs/`: generated runtime artifacts and logs

Keep original plate media in `data/raw/` and avoid destructive edits.

## Annotation Preparation

Use `scripts/prepare_annotation_folder.py` to create a clean annotation-ready image folder and manifest.

This script:

- copies supported images from a raw folder
- renames them into a consistent sequence such as `usm_img_000001`
- creates a CSV manifest with original file names and placeholder annotation fields

This is useful when source images have messy names or come from mixed devices and uploads.

## Group-Based Splits

Use `scripts/make_group_splits.py` when you want train, validation, and test assignments that respect groups such as plate identity.

This matters because random image-level splitting can leak near-duplicate frames of the same vehicle across different splits.

The current guidance is to split by a grouping field like `plate_id` when possible.

## OCR Crop Generation

There are two main crop-building helpers:

### `scripts/export_gt_crops.py`

Use this when you already have YOLO labels and want cropped plate images from them.

### `scripts/build_ocr_from_yolo_export.py`

Use this when you want to create:

- cropped OCR images
- a manifest CSV for OCR labeling or review

The generated manifest includes crop paths, source image paths, class information, and empty fields for `true_text`, OCR guesses, and notes.

After crops are generated, use the manual labeling process in `docs/ocr-labeling-workflow.md` to fill `true_text` from the crop images.

## Dataset Config

`configs/detector_data.yaml` points to a YOLO-style dataset layout and currently uses one class:

- `plate_number`

Keep detector class naming aligned with the dataset export and model training configuration.

Current detector split layout in the workspace:

- `data/images/train`, `data/labels/train`
- `data/images/val`, `data/labels/val`
- `data/images/test`, `data/labels/test`

Some YOLO label files may be intentionally empty because they came from Roboflow null-image negatives. Do not assume every empty `.txt` file is a missing annotation without checking the source export context first.

## OCR Evaluation Assets

The OCR side currently has both split-specific and aggregated assets.

Split-specific truth files:

- `data/ocr/train_crops/` with `data/ocr/train_labels.csv`
- `data/ocr/val_crops/` with `data/ocr/val_labels.csv`
- `data/ocr/test_crops/` with `data/ocr/test_labels.csv`

Aggregated OCR evaluation assets:

- `data/ocr/all_crops/`
- `data/ocr/all_labels.csv`

`all_labels.csv` includes:

- `image_path`
- `true_text`
- `split`

This aggregated set is useful when running OCR evaluation across the full crop dataset without changing the existing train, validation, and test crop folders.

## Practical Recommendations

- preserve originals in `data/raw/`
- put cleaned annotation inputs in `data/interim/`
- keep OCR labels and manifests in `data/ocr/` or `data/metadata/`
- avoid committing temporary experiment artifacts into source folders
- treat plate images and labels as sensitive project data
