# Codex Handoff Notes

This note is for future development sessions on this repository.

Use it as short project memory so implementation work stays aligned with the current thesis and demo direction.

## What This Project Is Now

This is a local-first two-stage license plate recognition app:

1. YOLO detects the plate region.
2. OCR reads the cropped plate text.
3. Stable `entry` and `exit` reads are turned into session events.
4. SQLite stores the resulting operational data.

The current app already includes session tracking, role-aware cameras, video upload inference, and a FastAPI dashboard.

Vehicle registration and profile-linking context now also exists.

Before extending that area, read:

- `docs/vehicle-registration-feature.md`

## Current Scope To Preserve

- keep one detector class: `plate_number`
- keep one primary final plate result per frame
- keep recognition logic separate from entry and exit session logic
- prefer pretrained OCR engines first
- keep config in YAML instead of hardcoding behavior into runtime code
- keep the app honest when weights, OCR dependencies, or storage are unavailable
- keep the system local-first so recognition and session logging do not depend on the internet

## Important Architectural Rule

Do not mix session business logic directly into:

- `src/core/detector.py`
- `src/core/ocr_engine.py`
- `src/core/pipeline.py`
- `src/services/camera_service.py`

Recognition should produce stable plate events.

The session layer should decide:

- whether this is an `entry` or `exit` event
- whether to open a session
- whether to close a session
- whether to ignore the event because of cooldown, low quality, ambiguity, or duplication

## Current Runtime Flow

The current working flow is:

1. a camera role such as `entry` or `exit` captures frames
2. detector and OCR produce a cleaned candidate result
3. the result stabilizer confirms the read is stable enough
4. the pipeline emits a recognition event
5. `SessionService` decides whether to open, close, ignore, or log the event
6. `StorageService` persists recognition events, sessions, and unmatched exits to SQLite
7. the dashboard and API expose status, recent events, active sessions, history, and performance snapshots

## Session Rules To Preserve

The current implementation assumes:

- only `entry` and `exit` are actionable camera roles for session decisions
- one open session per plate at a time
- stable repeated reads inside cooldown do not create duplicate actions
- low-quality or ambiguous near-match reads are logged as ignored decisions
- unmatched exits are recorded instead of silently dropped

Be careful when changing thresholds in `configs/app_settings.yaml`, because they directly affect whether reads become session events.

## Best Next Implementation Order

When continuing development, prefer this order:

1. keep the current recognition and session flow working
2. expand automated coverage for camera runtime, video uploads, and entry or exit lifecycle regressions
3. tighten API response modeling and docs
4. add database lifecycle support such as migrations or versioning
5. improve moderation and operator workflows
6. keep iterating on recognition quality for difficult cases
7. only after the local system is stable, consider optional sync or online reporting layers

## Files To Touch First For Current Work

Likely first-pass files:

- `configs/app_settings.yaml`
- `src/app.py`
- `src/bootstrap.py`
- `src/services/session_service.py`
- `src/services/storage_service.py`
- `src/services/vehicle_registry_service.py`
- `src/api/routes.py`
- `src/api/settings_support.py`
- `src/api/upload_support.py`
- `src/api/dashboard_support.py`
- `src/api/schemas.py`
- `templates/index.html`
- `static/js/app.js`
- `docs/CONTEXT.md`
- `docs/missing-pieces.md`

## Detector Runtime Reminder

The current config defaults to an ONNX detector runtime:

- backend: `onnxruntime`
- ONNX weights path: `models/detector/yolo26nbest.onnx`

The older Ultralytics path is still supported:

- PT weights path: `models/detector/yolo26nbest.pt`

If detector readiness looks wrong, check both the configured backend and the corresponding weights file.

## Things To Avoid

- do not hardcode absolute local paths
- do not commit `data/`, generated `outputs/`, or model weights
- do not collapse recognition state and session state into one service
- do not let repeated frame detections create duplicate entry or exit logs
- do not pretend OCR is perfectly reliable
- do not break the current graceful-degradation behavior
- do not make the online layer a runtime dependency if sync work is added later

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

Aim for a solid thesis and demo system, not a perfect commercial LPR product.

Success looks like:

- the app reads plates reasonably well
- stable reads become recognition events
- `entry` opens a session
- `exit` closes the matching session
- duplicates are controlled
- the UI, logs, and API make the flow understandable during a demo

## If Starting Fresh In A Future Session

Quick checklist:

1. read `README.md`
2. read `docs/architecture.md`
3. read `docs/CONTEXT.md`
4. read `docs/missing-pieces.md`
5. inspect `src/app.py`, `src/services/session_service.py`, `src/services/storage_service.py`, and `src/api/routes.py`
6. confirm whether the user wants testing, hardening, recognition tuning, or UI work first

## Communication Reminder

The user cares about whether the real flow is possible, demoable, and honest about current limitations.

When helping later:

- keep explanations concrete
- separate prototype feasibility from production-grade claims
- prefer simple implementations that preserve momentum
- protect the current working recognition and session flow while extending it
