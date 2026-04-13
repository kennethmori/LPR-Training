# OCR Labeling Workflow

## Purpose

This document explains how we manually fill `true_text` in the OCR truth CSV files from cropped plate images.

This is the ground-truth labeling step for OCR evaluation. Detector boxes alone are not enough. Each crop still needs the actual visible plate value written into the CSV.

## Files Involved

- `data/ocr/train_crops/`, `data/ocr/val_crops/`, `data/ocr/test_crops/`: cropped plate images
- `data/ocr/train_labels.csv`, `data/ocr/val_labels.csv`, `data/ocr/test_labels.csv`: split-specific OCR truth files
- `data/ocr/all_crops/`: aggregated crop folder for evaluation convenience
- `data/ocr/all_labels.csv`: aggregated OCR truth file with `image_path,true_text,split`
- `outputs/`: optional helper artifacts for zoomed or enhanced review when needed

## Expected Labeling Rule

For each crop:

- read the plate text directly from the crop image
- write exactly what is visible on the plate into `true_text`
- use manual visual inspection as the source of truth
- do not invent a normalized format unless the team explicitly decides to normalize all labels later

This means:

- regular motorcycle and vehicle plates should be copied as seen
- temporary registration plates are still valid labels
- if the visible plate uses a hyphenated temporary format, keep the value consistent with the dataset convention already used in `train_labels.csv`

Current practical convention in this repo:

- many temporary registrations are stored without the hyphen
- example visible plate: `1201-668394`
- stored CSV value: `1201668394`

## Manual Review Flow

1. Open the relevant truth CSV such as `data/ocr/train_labels.csv`.
2. Open the matching crop referenced by `image_path`.
3. Read the crop directly and transcribe the visible plate text.
4. If the crop is difficult, use enlarged helper views or generated review images.
5. Write the confirmed value back into the CSV.
6. Prefer a short review list for suspicious rows instead of relabeling every row from scratch.

## Review Aids

Helper images are optional aids for difficult rows, not the primary truth source.

Recommended order:

1. read the actual crop file first
2. create or use enlarged review copies when needed
3. only use derived images to support the manual reading of the original crop

This helps when:

- the crop is too small
- the plate is rotated
- the temporary plate format is easy to misread
- a previously entered value looks suspicious

## What Counts As Unresolved Or Risky

A row still needs follow-up when any of these are true:

- `true_text` is blank
- the crop file referenced by `image_path` does not exist
- the visible text is too ambiguous to label confidently
- the currently stored label looks suspicious after re-checking the crop

Do not force a guess just to reduce the blank count. If a value is uncertain, track it for another pass.

## Aggregated Evaluation Set

The repo now also includes an aggregated OCR evaluation dataset:

- `data/ocr/all_crops/`
- `data/ocr/all_labels.csv`

This combined set is for evaluation convenience only. It does not replace the current split-specific crop folders and CSV files.

## Current Status Snapshot

Dataset status after the latest manual labeling pass:

- `train_labels.csv`: fully paired with `train_crops`
- `val_labels.csv`: fully paired with `val_crops`
- `test_labels.csv`: fully paired with `test_crops`
- `all_labels.csv`: fully paired with `all_crops`

Current crop and label counts in the workspace:

- train: `334`
- val: `105`
- test: `97`
- all combined: `536`

The current OCR truth files were completed through manual visual inspection rather than OCR autofill.

## Quality Notes

Common failure patterns during manual transcription:

- confusing `M` with `H`
- confusing `U` with `V`
- confusing `O` with `Q` or `0`
- missing one character on temporary plates
- reading a temporary plate number but forgetting the dataset stores it without the hyphen

When a label looks suspicious:

- compare it against the crop again
- use an enlarged review image if needed
- prefer a tracked uncertainty list over silently trusting a low-confidence value

## Recommended Next Steps

- use `scripts/evaluate_ocr.py` against the split-specific or aggregated OCR truth files
- keep the split-specific crop folders unchanged so train, validation, and test evaluations stay reproducible
- if needed later, build a lightweight labeling or review utility instead of doing repeated CSV-only editing
