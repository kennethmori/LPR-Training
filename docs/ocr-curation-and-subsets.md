# OCR Curation And Confidence-Based Subsets

## Purpose

This document records the OCR curation work completed in this workspace after the initial full-crop OCR evaluation.

It explains:

- why the original OCR crop set is noisy
- which curated OCR subsets were created
- what confidence thresholds were used
- which scripts were added for reproducible curation
- how the resulting evaluation numbers should be interpreted

## Why Curation Was Needed

The original aggregated OCR dataset at:

- `data/ocr/all_crops/`
- `data/ocr/all_labels.csv`

was derived from plate crops originally intended to support detector work rather than OCR-only benchmarking.

That means the crop set contains a mix of:

- clearly readable plates
- distant plates
- blurry plates
- partially visible plates
- tilted or rotated plates
- temporary or unusual plate layouts

Because of that, OCR performance on the full aggregated crop set reflects both:

- OCR recognizer quality
- crop-quality noise from detector-oriented data preparation

## OCR Engine Used

The OCR evaluation and curation work in this phase used:

- `PaddleOCR`
- recognizer: `en_PP-OCRv5_mobile_rec`
- CPU execution
- `cpu_threads: 8`

Relevant config path:

- `configs/app_settings.yaml`

Relevant OCR engine path:

- `src/core/ocr_engine.py`

## Scripts Added For This Workflow

The following scripts were added to support reproducible OCR subset creation and evaluation:

- `scripts/run_ocr_predictions.py`
- `scripts/run_ocr_evaluation.py`
- `scripts/report_ocr_errors.py`
- `scripts/create_readable_ocr_dataset.py`
- `scripts/create_confidence_dataset.py`

These scripts make it possible to:

- run OCR on a crop folder
- generate prediction CSVs
- compute OCR metrics
- build readable-only subsets
- build weak-confidence subsets for failure analysis

## Full Aggregated OCR Result

The full aggregated OCR run used:

```bash
python scripts/run_ocr_evaluation.py data/ocr/all_crops data/ocr/all_labels.csv --output-dir outputs/metrics --prefix all_paddle_en_v5_threads8
```

Result on all `536` crops:

- samples: `536`
- exact match accuracy: `0.2257`
- character accuracy: `0.5282`
- average edit distance: `3.0485`

Key interpretation:

- this is the realistic OCR baseline on the noisy detector-derived crop set
- it is not a clean upper-bound OCR benchmark

## Confidence Threshold Counts

From the full aggregated PaddleOCR run:

- confidence `>= 0.80`: `185` predictions, `105` exact matches
- confidence `>= 0.85`: `146` predictions, `96` exact matches
- confidence `>= 0.90`: `95` predictions, `75` exact matches
- confidence `>= 0.95`: `49` predictions, `45` exact matches

These counts were used to guide readable-only subset creation.

## Readable-Only Subsets Created

Readable subsets were created conservatively using:

- exact OCR match with the ground truth
- confidence threshold at or above the chosen value

### 95% Readable Subset

Files:

- `data/ocr/readable_crops`
- `data/ocr/readable_labels.csv`
- `data/ocr/readable_manifest.csv`

Creation rule:

- exact match
- confidence `>= 0.95`

Final count:

- `45` crops

Evaluation result:

- samples: `45`
- exact match accuracy: `1.0`
- character accuracy: `1.0`
- average edit distance: `0.0`

Important note:

- this perfect score is expected because the subset was intentionally curated from exact-match high-confidence samples
- it should be presented as a very-readable benchmark subset, not as an unbiased generalization test

### 85% Readable Subset

Files:

- `data/ocr/readable_crops_85`
- `data/ocr/readable_labels_85.csv`
- `data/ocr/readable_manifest_85.csv`

Creation rule:

- exact match
- confidence `>= 0.85`

Final count:

- `96` crops

Evaluation result:

- samples: `96`
- exact match accuracy: `1.0`
- character accuracy: `1.0`
- average edit distance: `0.0`

### 80% Readable Subset

Files:

- `data/ocr/readable_crops_80`
- `data/ocr/readable_labels_80.csv`
- `data/ocr/readable_manifest_80.csv`

Creation rule:

- exact match
- confidence `>= 0.80`

Final count:

- `105` crops

Evaluation result:

- samples: `105`
- exact match accuracy: `1.0`
- character accuracy: `1.0`
- average edit distance: `0.0`

## Weak-Confidence Failure Subset

To study OCR failure cases directly, a weak-confidence subset was also created.

Files:

- `data/ocr/weak_crops_80`
- `data/ocr/weak_labels_80.csv`
- `data/ocr/weak_manifest_80.csv`

Creation rule:

- confidence `<= 0.80`
- mismatches allowed

Final count:

- `351` crops

Within this weak subset:

- exact matches: `16`
- non-exact cases: `335`

Evaluation result:

- samples: `351`
- exact match accuracy: `0.0456`
- character accuracy: `0.3166`
- average edit distance: `4.3362`

This subset is useful for:

- identifying OCR failure modes
- showing where the recognizer breaks down
- contrasting readable versus difficult crops in the report

## Main Failure Patterns Observed

From the weak-confidence and full-set error reports, the main OCR problems were:

- missing trailing characters
- empty predictions on difficult crops
- `M/H` confusion
- `8/B` confusion
- `0/O` confusion
- short outputs from longer true plates
- noisy outputs on temporary or unusual plate formats

Example interpretation:

- readable high-confidence crops are usually decoded correctly
- low-confidence crops often reflect blur, distance, tilt, occlusion, or visually ambiguous characters

## Normalization Effect

The OCR post-processing and normalization step in this repo:

- uppercases text
- removes spaces
- removes non-alphanumeric characters

For the PaddleOCR full-set run, normalization substantially improved the reported OCR result:

- raw exact match accuracy: `0.0504`
- cleaned exact match accuracy: `0.2257`

Normalization helped mostly by removing formatting noise such as internal spaces, but it did not fix true OCR misreads.

## Suggested Reporting Language

A concise thesis-style interpretation is:

The OCR crop dataset is noisy because it was derived from detector-oriented plate crops rather than curated solely for OCR legibility. As a result, the full OCR evaluation reflects both recognizer performance and crop-quality limitations. To support clearer analysis, additional confidence-based subsets were created: readable-only sets at 80%, 85%, and 95% confidence for best-case OCR behavior, and a weak-confidence set at 80% and below for failure analysis.

## Reproducible Commands

Full aggregated OCR run:

```bash
python scripts/run_ocr_evaluation.py data/ocr/all_crops data/ocr/all_labels.csv --output-dir outputs/metrics --prefix all_paddle_en_v5_threads8
```

Create 95% readable subset:

```bash
python scripts/create_readable_ocr_dataset.py data/ocr/all_labels.csv outputs/metrics/all_paddle_en_v5_threads8_predictions.csv --output-dir data/ocr/readable_crops --labels-csv data/ocr/readable_labels.csv --manifest-csv data/ocr/readable_manifest.csv --min-confidence 0.95
```

Create 85% readable subset:

```bash
python scripts/create_readable_ocr_dataset.py data/ocr/all_labels.csv outputs/metrics/all_paddle_en_v5_threads8_predictions.csv --output-dir data/ocr/readable_crops_85 --labels-csv data/ocr/readable_labels_85.csv --manifest-csv data/ocr/readable_manifest_85.csv --min-confidence 0.85
```

Create 80% readable subset:

```bash
python scripts/create_readable_ocr_dataset.py data/ocr/all_labels.csv outputs/metrics/all_paddle_en_v5_threads8_predictions.csv --output-dir data/ocr/readable_crops_80 --labels-csv data/ocr/readable_labels_80.csv --manifest-csv data/ocr/readable_manifest_80.csv --min-confidence 0.80
```

Create weak-confidence subset:

```bash
python scripts/create_confidence_dataset.py data/ocr/all_labels.csv outputs/metrics/all_paddle_en_v5_threads8_predictions.csv --output-dir data/ocr/weak_crops_80 --labels-csv data/ocr/weak_labels_80.csv --manifest-csv data/ocr/weak_manifest_80.csv --max-confidence 0.80 --allow-mismatches
```

Evaluate weak-confidence subset:

```bash
python scripts/run_ocr_evaluation.py data/ocr/weak_crops_80 data/ocr/weak_labels_80.csv --output-dir outputs/metrics --prefix weak_80_paddle_en_v5_threads8
```
