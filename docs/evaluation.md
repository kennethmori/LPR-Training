# Evaluation

## Evaluation Philosophy

This project separates evaluation into distinct stages:

- detector performance
- OCR performance
- end-to-end recognition performance

That separation is important because successful plate localization does not guarantee correct text recognition.

## OCR Evaluation

Use `scripts/evaluate_ocr.py` to compare OCR predictions with ground truth text labels.

Expected inputs:

- truth CSV
- predictions CSV

Required join key:

- `image_path`

Main metrics returned by the script:

- sample count
- exact match accuracy
- character accuracy
- average edit distance

Character accuracy is based on Levenshtein edit distance across the merged dataset.

Current ground-truth options in this repo:

- split-specific OCR truth files: `data/ocr/train_labels.csv`, `data/ocr/val_labels.csv`, `data/ocr/test_labels.csv`
- aggregated OCR truth file: `data/ocr/all_labels.csv`

For the current project stage, OCR can be evaluated directly against these prepared crop-and-label datasets even without training a custom OCR model. The current workflow is:

1. run the OCR engine on the crop images
2. save predictions with `image_path,predicted_text`
3. compare predictions against one of the ground-truth CSV files using `scripts/evaluate_ocr.py`

## End-to-End Evaluation

Use `scripts/evaluate_end_to_end.py` to evaluate the full detector-plus-OCR pipeline.

Expected columns in the input CSV:

- `detected`
- `true_text`
- `predicted_text`
- `pipeline_time_ms`

Main metrics returned by the script:

- sample count
- detection rate
- end-to-end exact-match accuracy
- average pipeline time in milliseconds

## Training Helper

Use `scripts/train_detector.py` to fine-tune the detector with Ultralytics YOLO.

Example:

```bash
python scripts/train_detector.py --data configs/detector_data.yaml --model yolo26s.pt
```

Recommended baseline from the repo:

- main choice: `yolo26s.pt`
- lighter fallback: `yolo26n.pt`

## Reporting Guidance

When presenting results, keep these categories separate:

- detector-only metrics
- OCR-only metrics
- end-to-end exact match
- runtime measurements

Also keep Colab training and evaluation context separate from local prototype runtime numbers, since hardware conditions differ.

Practical status in the current workspace:

- OCR evaluation data is ready
- detector fine-tuning data is prepared in YOLO layout
- some empty YOLO labels may be intentional null-image negatives from Roboflow rather than annotation failures
