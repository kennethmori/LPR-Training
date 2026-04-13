# Phase 1 Plan

## Purpose

This document is the full working plan for Phase 1 of the project.

Phase 1 is the recognition-readiness phase. Its job is to prove that the current detector-plus-OCR pipeline is strong enough to support the later campus entry and exit system.

This phase should answer these questions clearly:

- how good is the detector
- how good is the OCR stage
- how good is the full end-to-end pipeline
- what error patterns remain before session tracking is added

## Phase 1 Goal

The goal of Phase 1 is to complete and document three separate evaluations:

1. detector-only performance
2. OCR-only performance
3. end-to-end detector-plus-OCR performance

At the end of Phase 1, the team should have:

- trained detector weights
- saved evaluation outputs
- baseline metrics for reporting
- a short list of recognition weaknesses to improve later

Phase 1 should not yet focus on entry and exit session tracking. That belongs to later phases.

## Scope

Included in Phase 1:

- detector fine-tuning
- detector validation and test evaluation
- OCR evaluation on prepared crop truth data
- full pipeline evaluation
- error analysis
- metric reporting
- documentation of findings

Not included in Phase 1:

- dual-camera workflow
- session service
- SQLite session storage
- session-oriented API routes
- entry and exit monitoring UI

## Current Starting Point

The repository already has the minimum required assets to start Phase 1.

Detector dataset:

- `data/images/train` and `data/labels/train`
- `data/images/val` and `data/labels/val`
- `data/images/test` and `data/labels/test`
- `configs/detector_data.yaml`

OCR evaluation dataset:

- `data/ocr/train_crops` with `data/ocr/train_labels.csv`
- `data/ocr/val_crops` with `data/ocr/val_labels.csv`
- `data/ocr/test_crops` with `data/ocr/test_labels.csv`
- aggregated OCR set in `data/ocr/all_crops` with `data/ocr/all_labels.csv`

Existing helper scripts:

- `scripts/train_detector.py`
- `scripts/evaluate_ocr.py`
- `scripts/evaluate_end_to_end.py`

Important practical note:

- the OCR truth files are ready for evaluation use
- detector labels are already arranged in YOLO layout
- some empty YOLO label files may be intentional Roboflow null-image negatives

## Success Criteria

Phase 1 is successful when all of the following are complete:

- detector fine-tuning has been run and the best detector checkpoint is saved
- detector results on validation and test are documented
- OCR predictions have been generated and scored against truth CSV files
- end-to-end predictions have been generated and scored
- failure cases are reviewed manually
- a short baseline report exists for detector, OCR, and end-to-end performance

## Deliverables

At the end of Phase 1, the repo or outputs folder should contain:

- trained detector weights in `models/detector/best.pt` or an equivalent saved experiment output
- Ultralytics training results and plots
- OCR predictions CSV files for at least validation and test
- end-to-end evaluation CSV
- detector, OCR, and end-to-end metric summaries
- a documented list of major failure patterns

## Work Breakdown

Phase 1 is best executed in four workstreams:

1. detector preparation and fine-tuning
2. detector evaluation
3. OCR evaluation
4. end-to-end evaluation and reporting

## Workstream 1: Detector Preparation And Fine-Tuning

### Objective

Fine-tune the YOLO detector from a pretrained checkpoint and produce a reliable `best.pt` baseline.

### Inputs

- `configs/detector_data.yaml`
- detector dataset in `data/images` and `data/labels`
- pretrained YOLO checkpoint such as `yolo26s.pt`

### Tasks

1. Confirm that `configs/detector_data.yaml` points to the current split layout.
2. Confirm that the detector class name remains `plate_number`.
3. Run a quick dataset sanity pass before training:
   - image and label pairing
   - label format consistency
   - intentional empty detector labels understood as Roboflow null-image negatives where applicable
4. Train the baseline detector with `yolo26s.pt`.
5. Save training outputs for later reporting.

### Baseline Command

```bash
python scripts/train_detector.py --data configs/detector_data.yaml --model yolo26s.pt --epochs 80 --imgsz 640 --batch 16
```

### Baseline Hyperparameters

Start with one stable baseline before tuning.

Recommended baseline values:

- model: `yolo26s.pt`
- epochs: `80`
- image size: `640`
- batch size: `16`
- patience: `20`

These values are a good first pass because they balance training cost and expected detector quality.

### Optional Variants

Use these only when needed:

- lower-memory fallback: `yolo26n.pt`
- larger image size if small plates need help
- longer training if metrics are still improving at the end

### Hyperparameter Tuning Plan

Hyperparameter tuning should be controlled and incremental.

Do not tune many things at the same time in the first round. Change one major factor at a time so the result is interpretable.

Recommended tuning order:

1. model size
2. image size
3. training length and patience
4. batch size
5. inference-side detector settings for evaluation

#### Stage 1: Model Size

Compare these only if resources allow:

- `yolo26n.pt`
- `yolo26s.pt`

Goal:

- check whether the smaller model loses too much recall on small or angled plates

Recommendation:

- keep `yolo26s.pt` as the primary baseline unless hardware forces a smaller model

#### Stage 2: Image Size

Candidate values:

- `640`
- `768`
- `960`

What this changes:

- larger image sizes may help with small or distant plates
- larger image sizes also increase training cost and inference cost

Recommendation:

- start with `640`
- try `768` next if detector misses small plates often
- use `960` only if results justify the extra cost

#### Stage 3: Epochs And Patience

Candidate values:

- epochs: `80`, `100`, `120`
- patience: `20`, `30`

What this changes:

- more epochs may help if validation metrics are still rising
- too many epochs can waste time or overfit

Recommendation:

- keep the first run at `80`
- move to `100` or `120` only if the best run still improves near the end

#### Stage 4: Batch Size

Candidate values:

- `8`
- `16`
- `24` or `32` if hardware allows

What this changes:

- training stability
- GPU memory use
- speed per epoch

Recommendation:

- use the largest stable batch size that fits your hardware
- if using Colab or limited GPU memory, `8` or `16` is usually safer

#### Stage 5: Inference-Side Detector Settings

These are not training hyperparameters, but they matter during detector evaluation and end-to-end evaluation.

Track at least:

- confidence threshold
- IoU threshold for NMS

Recommended starting values:

- confidence threshold: `0.25`
- IoU threshold: `0.45`

If the detector produces too many weak false positives:

- raise confidence slightly

If the detector misses useful boxes:

- lower confidence slightly and inspect the effect manually

### Suggested Detector Experiment Matrix

A practical first tuning matrix is:

1. `yolo26s`, `640`, `80`, batch `16`
2. `yolo26s`, `768`, `80`, batch `16`
3. `yolo26s`, `640`, `100`, batch `16`
4. `yolo26n`, `640`, `80`, batch `16`

If only one extra run is possible, prioritize:

- `yolo26s`, `768`, `80`, batch `16`

### Detector Run Tracking

For every fine-tuning run, record:

- run name
- model checkpoint used
- epochs
- image size
- batch size
- patience
- precision
- recall
- mAP50
- mAP50-95
- notes on visible failure patterns

Recommended tracking table format:

```text
run_name,model,imgsz,epochs,batch,patience,precision,recall,map50,map50_95,notes
yolo26s_640_e80,yolo26s.pt,640,80,16,20,...,...,...,...,...
```

### Outputs

- training logs
- loss curves
- precision and recall curves
- `best.pt`

### Risks

- overfitting if the split contains many near-duplicate scenes
- undertraining if the epoch count is too conservative
- misleading results if null-image negatives are misunderstood as annotation mistakes

## Workstream 2: Detector Evaluation

### Objective

Measure the quality of plate localization separately from OCR.

### Questions To Answer

- does the detector localize plates reliably on `val`
- does it generalize on `test`
- what kinds of images still fail

### Tasks

1. Review Ultralytics validation metrics after training.
2. Save or summarize key detector metrics:
   - precision
   - recall
   - mAP50
   - mAP50-95
3. Run the trained detector on held-out samples.
4. Manually review false positives, false negatives, and weak crops.
5. Write a short detector-only summary for reporting.

### Detector Selection Rule

Choose the detector run that gives the best balance of:

- validation quality
- test generalization
- visible crop usefulness for OCR
- practical runtime cost

Do not choose only by one metric if another run creates clearly better plate crops for OCR.

### Recommended Manual Review Categories

- low light
- motion blur
- far-distance plates
- steep angles
- partial occlusion
- parked motorcycles with cluttered backgrounds

### Deliverables

- detector-only metric summary
- a folder or note set of failure examples
- decision on whether `best.pt` is good enough to proceed

## Workstream 3: OCR Evaluation

### Objective

Measure OCR quality independently using the prepared crop truth files.

### Important Clarification

Phase 1 does not require training a custom OCR model.

The current plan is to evaluate the existing pretrained OCR stage against the manually prepared crop truth CSV files.

### Truth Sources

You can use either:

- split-specific truth files such as `data/ocr/val_labels.csv` and `data/ocr/test_labels.csv`
- aggregated truth file `data/ocr/all_labels.csv`

Recommended default:

- use `val` and `test` separately first
- use `all_labels.csv` only for an overall aggregate summary if helpful

### Tasks

1. Run the OCR engine over `val_crops` and save predictions.
2. Run the OCR engine over `test_crops` and save predictions.
3. Save predictions with:
   - `image_path`
   - `predicted_text`
4. Score them using `scripts/evaluate_ocr.py`.
5. Review the worst OCR errors manually.

### OCR Evaluation Settings To Track

Even without training a custom OCR model, you should still track evaluation-relevant OCR settings.

At minimum, record:

- OCR engine used first
- fallback engine used if primary OCR is unavailable
- crop preprocessing behavior if changed
- post-processing rules active during the run

Useful OCR-side experiment variants:

- original crop only
- resized crop
- resized plus light contrast enhancement
- raw OCR text versus cleaned post-processed text

Recommendation:

- start with the repo's default OCR path
- do not add many preprocessing changes until you have one clean baseline result

### OCR Experiment Matrix

A simple first OCR matrix is:

1. default OCR on `val`
2. default OCR on `test`
3. optional preprocessing-enhanced OCR on a smaller review subset if baseline errors are concentrated in blur or low contrast

If preprocessing is tested, compare it against the same truth split and keep the metric outputs separate.

### Output Format Requirement

Each OCR prediction CSV should look like:

```text
image_path,predicted_text
data/ocr/val_crops/example.jpg,ABC1234
```

### Required Metric Outputs

- sample count
- exact match accuracy
- character accuracy
- average edit distance

### Required Error Analysis

Record at least these OCR failure categories:

- `M` versus `H`
- `U` versus `V`
- `O` versus `Q` versus `0`
- temporary plates with long numeric sequences
- blurred or rotated crops

### Gap To Be Aware Of

The repo already has the scorer script, but it may still need a prediction-export workflow if the team does not yet have one saved.

If no OCR prediction runner exists yet, Phase 1 should include adding a small helper script that:

- reads crop images
- runs the current OCR engine
- writes `image_path,predicted_text`

That script should be lightweight and evaluation-oriented, not a new training pipeline.

## Workstream 4: End-To-End Evaluation

### Objective

Measure realistic overall recognition quality when the detector and OCR operate together.

### Why This Matters

Good OCR on perfect crops does not prove that the full system works well on raw images.

The end-to-end check is where the real pipeline quality shows up.

### Tasks

1. Run the detector and OCR pipeline on held-out images or evaluation samples.
2. Save one result row per evaluated image.
3. Include the fields required by `scripts/evaluate_end_to_end.py`.
4. Score the results.
5. Review combined detector-plus-OCR failures.

### End-To-End Evaluation Settings To Track

For each end-to-end run, track:

- detector checkpoint used
- detector confidence threshold
- detector IoU threshold
- OCR engine path used
- post-processing rules active
- whether stabilization was enabled

These settings matter because end-to-end quality can change even when detector weights stay the same.

### Required Columns

- `detected`
- `true_text`
- `predicted_text`
- `pipeline_time_ms`

### Recommended Extra Columns

- `image_path`
- `camera_source`
- `detector_confidence`
- `ocr_confidence`
- `raw_text`
- `cleaned_text`

### Deliverables

- end-to-end results CSV
- end-to-end exact match accuracy
- detection rate
- runtime summary

## Reporting Plan

Phase 1 reporting should keep the three evaluation layers separate.

The final Phase 1 summary should include:

- detector-only metrics
- OCR-only metrics
- end-to-end metrics
- short interpretation of what each result means

Do not collapse everything into one headline number.

Recommended report structure:

1. Detector results
2. OCR results
3. End-to-end results
4. Error analysis
5. Conclusion on readiness for Phase 2

## Recommended Output Locations

Suggested output structure for evaluation artifacts:

- `outputs/metrics/` for final metric summaries
- `outputs/predictions/ocr_val_predictions.csv`
- `outputs/predictions/ocr_test_predictions.csv`
- `outputs/predictions/end_to_end_results.csv`
- `outputs/review/` for selected failure cases

If these folders do not exist yet, they can be created during Phase 1 implementation.

Recommended supporting files:

- `outputs/metrics/detector_runs.csv`
- `outputs/metrics/ocr_runs.csv`
- `outputs/metrics/end_to_end_runs.csv`

These tracking files should be used to compare experiments instead of relying on memory or screenshot-only notes.

## Execution Sequence

The practical order should be:

1. detector sanity check
2. detector fine-tuning
3. detector validation review
4. OCR prediction generation on `val`
5. OCR scoring on `val`
6. OCR prediction generation on `test`
7. OCR scoring on `test`
8. end-to-end evaluation run
9. final error review
10. Phase 1 summary writing

## Suggested Checklist

Use this checklist to track completion.

### Detector

- detector config checked
- detector dataset pairing checked
- fine-tuning run completed
- `best.pt` saved
- validation metrics reviewed
- test behavior reviewed manually
- at least one tuned comparison run completed
- detector experiment results logged

### OCR

- OCR truth CSVs verified
- OCR predictions generated for `val`
- OCR predictions generated for `test`
- OCR metrics computed
- OCR failure examples reviewed
- OCR settings and experiment notes logged

### End-To-End

- end-to-end results CSV generated
- end-to-end metrics computed
- combined failure modes reviewed
- end-to-end settings logged

### Documentation

- Phase 1 metrics summarized
- important failure patterns documented
- readiness decision for Phase 2 written

## Decision Gate After Phase 1

Before starting Phase 2, the team should explicitly decide one of these:

1. recognition quality is good enough, proceed to entry and exit implementation
2. recognition quality is usable but needs one targeted detector improvement cycle
3. recognition quality is not yet stable enough, repeat Phase 1 improvements before adding session logic

That decision should be based on metrics and manual error review, not only on a few successful demo images.

## Tuning Guardrails

To keep Phase 1 manageable:

- do not tune detector architecture, image size, epochs, and batch size all at once
- do not start custom OCR training during this phase unless the project direction changes
- do not treat every small metric gain as worth the extra complexity
- prioritize the run that is easiest to explain, reproduce, and defend in a report

The purpose of Phase 1 is not unlimited optimization. The purpose is to establish a strong, documented baseline and make one or two justified improvements when they clearly help.

## Definition Of Done

Phase 1 is done when:

- a trained detector baseline exists
- detector metrics are documented
- OCR metrics are documented from the prepared crop truth files
- end-to-end metrics are documented
- major failure patterns are known
- the team has made a clear go or no-go decision for Phase 2

## Suggested Immediate Next Action

The most practical first action is:

1. run the detector fine-tuning baseline
2. prepare the OCR prediction-export workflow if it does not already exist
3. score OCR on `val` and `test`
4. produce one clean Phase 1 baseline report

That gives the project a strong technical foundation before any session-tracking code is added.
