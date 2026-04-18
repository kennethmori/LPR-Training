# Codex Handoff Notes

This note is for future development sessions on this repository.

Use it as a short project memory so implementation work stays aligned with the intended thesis/demo direction.

## What This Project Is

This is a two-stage license plate recognition prototype:

1. YOLO detects the plate region.
2. OCR reads the cropped plate text.

The current app is a recognition prototype first, not yet a full session-tracking system.

## Current Scope To Preserve

- keep one detector class: `plate_number`
- keep one primary final plate result per frame
- keep recognition logic separate from entry/exit session logic
- prefer pretrained OCR engines first
- keep config in YAML instead of hardcoding behavior into runtime code
- keep the app honest when weights or OCR dependencies are missing

## Important Architectural Rule

Do not mix session business logic directly into:

- `src/core/detector.py`
- `src/core/ocr_engine.py`
- `src/core/pipeline.py`
- `src/services/camera_service.py`

Recognition should produce stable plate events.

A separate session layer should decide:

- whether this is an `entry` or `exit` event
- whether to open a session
- whether to close a session
- whether to ignore the event because of cooldown or duplication

## Intended Future Flow

Target runtime flow:

1. `entry` camera sees plate
2. detector and OCR produce a cleaned result
3. result stabilizer confirms the plate is stable enough
4. session service opens a vehicle session
5. `exit` camera later reads the same plate
6. session service closes the most recent open session for that plate

This flow is feasible, but it depends on stabilization and cooldown rules to avoid duplicate events.

## Best Next Implementation Order

When continuing development, prefer this order:

1. keep the current recognition flow working
2. add camera roles such as `entry` and `exit`
3. define a clean recognition event payload
4. add `session_service.py`
5. add durable storage, preferably SQLite
6. extend API endpoints
7. extend the UI for active and completed sessions

Do not start by building a big database layer or a complex dashboard before the event flow is clear.

## Recommended Session Rules

Start simple:

- allow one open session per plate at a time
- stable `entry` read opens a session if none is open
- stable repeated `entry` reads inside cooldown do nothing
- stable `exit` read closes the most recent open session
- unmatched exits should be logged, not silently ignored

## Files To Touch First For Session Work

Likely first-pass files:

- `configs/app_settings.yaml`
- `src/services/result_service.py`
- `src/services/` for a new `session_service.py`
- `src/api/routes.py`
- `src/api/schemas.py`
- `src/app.py`
- `templates/index.html`
- `static/js/app.js`

If dual cameras are introduced, a camera manager may be cleaner than overloading the current single-camera service too much.

## Things To Avoid

- do not hardcode absolute local paths
- do not commit `data/`, generated `outputs/`, or model weights
- do not collapse recognition state and session state into one service
- do not let repeated frame detections create duplicate entry or exit logs
- do not pretend OCR is perfectly reliable
- do not break the current graceful-degradation behavior

## Dataset And Evaluation Reminder

This repo already has prepared detector and OCR evaluation assets locally, but those datasets are intentionally not pushed to GitHub.

Keep in mind:

- detector split uses `data/images/{train,val,test}` and matching labels
- OCR evaluation uses `data/ocr/train_crops`, `data/ocr/val_crops`, and `data/ocr/test_crops`
- aggregated OCR evaluation also exists at `data/ocr/all_crops`

Any future documentation should describe those paths, but not rely on GitHub shipping those files.

## GitHub Hygiene Reminder

The public repo is code-focused.

Before future pushes, double-check that these stay untracked:

- `data/`
- `outputs/` generated artifacts
- `.venv/`
- `models/detector/*.pt`
- export artifacts such as `.onnx`

Also prefer relative Markdown links only.

## Practical Goal

Aim for a solid thesis/demo system, not a perfect real-world commercial LPR product.

Success looks like:

- the app reads plates reasonably well
- stable reads become recognition events
- entry opens a session
- exit closes the session
- duplicates are controlled
- the UI and logs make the flow understandable during a demo

## If Starting Fresh In A Future Session

Quick checklist:

1. read `README.md`
2. read `docs/architecture.md`
3. read `docs/implementation-roadmap.md`
4. read `docs/session-flow.md`
5. inspect `src/app.py`, `src/core/pipeline.py`, and `src/services/result_service.py`
6. confirm whether the user wants session tracking, dual cameras, database work, or UI work first

## Communication Reminder

The user cares about whether the real flow is possible and demoable.

When helping later:

- keep explanations concrete
- separate prototype feasibility from production-grade claims
- prefer simple implementations that preserve momentum
- protect the current working recognition flow while extending it
