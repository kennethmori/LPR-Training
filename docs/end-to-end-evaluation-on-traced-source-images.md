# End-To-End Evaluation On Traced Source Images

## Purpose

This document records the first end-to-end evaluation runs performed after the OCR curation phase.

Unlike the OCR-only runs on pre-cropped plate images, this phase evaluates the full pipeline on uncropped source images:

- plate detection
- crop extraction
- OCR recognition
- text normalization

The goal is to measure how much performance changes once the detector and crop quality are back in the loop.

## Why This Evaluation Was Needed

The curated OCR subsets showed that `PaddleOCR` can read very clear plate crops reliably. However, those results alone do not measure real application behavior because the deployment pipeline starts from full images, not pre-cropped plates.

To evaluate the full system fairly, the curated OCR subsets were traced back to their original uncropped source images and YOLO label files.

This made it possible to run:

- detector -> crop -> OCR -> normalization

on the same cases that had already been analyzed during OCR curation.

## Source Datasets Used

The following traced source-image datasets were prepared:

- `data/end_to_end/readable_sources_95/`
- `data/end_to_end/readable_sources_85/`
- `data/end_to_end/readable_sources_80/`
- `data/end_to_end/weak_sources_80/`

This document records the first completed end-to-end runs for:

- `readable_sources_95`
- `readable_sources_85`

## Scripts Used

The following scripts were used for this phase:

- `scripts/create_uncropped_source_dataset.py`
- `scripts/run_end_to_end_predictions.py`
- `scripts/evaluate_end_to_end.py`

These scripts make it possible to:

- trace curated OCR crops back to their original source images
- run the detector and OCR stack on full images
- export a prediction CSV for each subset
- compute end-to-end metrics

## Output Format

The generated prediction CSV contains:

- `split`
- `source_image_path`
- `true_text`
- `predicted_text`
- `raw_text`
- `detected`
- `detector_confidence`
- `ocr_confidence`
- `detector_mode`
- `ocr_mode`
- `pipeline_time_ms`
- `note`

Current implementation note:

- the live pipeline returns one primary plate result per source image
- because of that, rows from images with multiple curated target plates were skipped during this evaluation phase

## Commands Used

### Readable 95%

```bash
python scripts/run_end_to_end_predictions.py data/end_to_end/readable_sources_95_manifest.csv outputs/metrics/end_to_end_readable_95_predictions.csv
python scripts/evaluate_end_to_end.py outputs/metrics/end_to_end_readable_95_predictions.csv
```

### Readable 85%

```bash
python scripts/run_end_to_end_predictions.py data/end_to_end/readable_sources_85_manifest.csv outputs/metrics/end_to_end_readable_85_predictions.csv
python scripts/evaluate_end_to_end.py outputs/metrics/end_to_end_readable_85_predictions.csv
```

## Results

### Readable 95%

- source rows written: `43`
- skipped multi-target rows: `2`
- detection rate: `0.9302`
- end-to-end exact-match accuracy: `0.7907`
- average pipeline time: `525.51 ms`

Output file:

- `outputs/metrics/end_to_end_readable_95_predictions.csv`

### Readable 85%

- source rows written: `94`
- skipped multi-target rows: `2`
- detection rate: `0.9362`
- end-to-end exact-match accuracy: `0.7021`
- average pipeline time: `455.95 ms`

Output file:

- `outputs/metrics/end_to_end_readable_85_predictions.csv`

## Interpretation

These runs show an important difference between OCR-only evaluation and end-to-end evaluation.

For OCR-only testing on curated crops:

- readable 95% subset scored perfectly by construction
- readable 85% subset also scored perfectly by construction

But once the same examples are evaluated starting from full source images, performance drops because additional failure points are introduced:

- the detector may miss the plate entirely
- the detector may localize the crop imperfectly
- the OCR engine may read a slightly degraded crop incorrectly

In other words, the OCR recognizer can work well on readable crops, but end-to-end system quality still depends heavily on:

- detector quality
- source-image framing
- plate size in the frame
- blur, angle, and distance

## What The Current Numbers Suggest

The `readable_sources_95` and `readable_sources_85` results show that:

- detection rate stayed similar across both sets
- final exact-match accuracy dropped when moving from the stricter `95%` readable set to the broader `85%` set

This is a useful report result because it shows that even among generally readable plates, broader inclusion still introduces enough variation to lower full-pipeline accuracy.

## Main Failure Types Observed

From the first `readable_sources_95` run, the main failure types were:

- no detection on some source images
- wrong OCR output after a successful detection
- character confusions such as `Q/0` or missing characters

Example failures included:

- `NJQ7798 -> NJ07798`
- `KAA3846 -> KA3846`
- several no-detection rows with empty predictions

These failures are consistent with the overall project finding that deployment quality depends on readable, stable, well-framed captures.

## Recommended Use In The Report

A good reporting structure is:

- OCR-only evaluation on noisy and curated crop subsets
- end-to-end evaluation on traced source images
- discussion of why full-image results are lower than crop-only results

A concise interpretation statement is:

The curated OCR subsets confirmed that the recognizer performs reliably when plate crops are very clear. However, end-to-end evaluation on the traced uncropped source images showed lower overall accuracy because the full pipeline reintroduces detector misses, imperfect crop localization, and source-image quality variation. This indicates that deployment performance depends not only on OCR quality, but also on robust detection and camera placement that consistently produces readable plate regions.

## Next Planned Runs

The next end-to-end runs to complete are:

- `readable_sources_80`
- `weak_sources_80`

These will allow comparison between:

- strict readable cases
- broader readable cases
- weak-confidence failure cases
