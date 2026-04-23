# Repository Guidelines

## Project Structure & Module Organization

This repository is a two-stage license plate recognition project: YOLO detects `plate_number`, then OCR reads cropped plate text.

- `src/` contains the app code.
- `src/app.py` is the FastAPI entry point and wires settings, detector, OCR, post-processing, pipeline, logging, and camera services.
- `src/core/` holds detector, cropper, OCR, post-processing, and pipeline logic.
- `src/services/` contains camera, tracking, logging, stabilization, session, storage, and vehicle-registry services.
- `src/api/` defines FastAPI routes, auth helpers, request or response schemas, and route support helpers.
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

- The default detector backend is `onnxruntime` with weights at `models/detector/yolo26nbest.onnx`.
- Ultralytics fallback still uses `models/detector/yolo26nbest.pt` when `detector.backend` is switched.
- Runtime events are appended to `outputs/demo_logs/events.jsonl`.
- The pipeline returns one primary plate result per frame and uses recent-history stabilization for camera mode.
- The app is designed to degrade gracefully when detector weights or OCR dependencies are missing; status endpoints and the UI should report the active mode honestly instead of pretending modules are ready.
- The live app supports role-based `entry` and `exit` camera flows with session open or close handling on top of recognition events.

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

## Frontend Architecture Guidelines

This project should stay server-rendered and framework-free for the UI layer, but the frontend should still follow a disciplined architecture instead of growing around one giant script.

- Treat the frontend as Jinja2 templates plus vanilla HTML, CSS, and JS; do not add React, Vue, or similar frameworks unless the task explicitly requires a stack change.
- Prefer a modular frontend structure under `static/js/` with clear responsibilities. In this repo, the dashboard entrypoint in `static/js/app.js` should stay a thin composition layer that imports focused modules such as `dashboard/store.js`, `dashboard/api.js`, `dashboard/camera_state.js`, `dashboard/navigation.js`, `dashboard/runtime.js`, and `dashboard/modals.js`.
- Keep one shared store per page domain. The dashboard should have a single dashboard state model, and the settings page should have a separate settings state model.
- Normalize all backend-driven payloads before rendering. Snapshot, SSE, upload, and latest-result responses should be mapped into one internal frontend state shape instead of each flow updating the DOM differently.
- Controllers should handle user events, API calls, and store updates only. They should not build HTML.
- Renderers should own one UI concept each, such as the overview, camera panel, recognition panel, active sessions, events, history, unmatched exits, debug panel, or settings form. Keep using `dashboard_panels.js` for section rendering and continue extracting additional renderers instead of expanding `app.js`.
- Reusable UI primitives such as badges, tables, empty states, modals, and button busy states should live in small shared component helpers instead of being reimplemented in multiple files.
- Utilities should own formatting, normalization, comparison helpers, DOM helpers, and constants. Keep these pure where possible.
- Avoid scattered DOM mutation. Outside of tightly scoped helper utilities, visible UI changes should flow through the shared store and the renderer that owns that section.
- Keep camera-role state, idle payload shaping, and recognition fallback smoothing out of `static/js/app.js`. In this repo, that responsibility belongs in `static/js/dashboard/camera_state.js`.
- Do not keep adding new logic to one large `app.js`. When touching large frontend files, prefer extracting the next clear module instead of extending the monolith further. `static/js/app.js` should remain below roughly 1000 lines, and if `dashboard_panels.js` keeps growing, split it by panel ownership rather than letting it become the next monolith.
- Keep dynamic sections rooted in stable containers in the templates. Templates should provide accessible shells, section roots, and tab panels, while renderers own the dynamic content within those roots.
- Prefer gradual refactors over full rewrites. The recommended extraction order is: shared store, normalization layer, stream or refresh controller, then section renderers, then reusable components.
- Keep CSS modular as well. In this repo, shared theme primitives belong in `static/css/base.css`, shared application styles stay in `static/css/style.css`, and page-specific rules should move into `static/css/pages/*.css` such as `static/css/pages/settings.css`.

## Backend Architecture Guidelines

The backend should stay modular and contract-driven as the project grows. The goal is to keep detection, OCR, tracking, sessions, storage, and API behavior predictable instead of letting route handlers or runtime glue become the default place for all logic.

- Keep one clear owner per backend concern. `src/core/` should own detector, crop, OCR, preprocessing, and pipeline logic; `src/services/` should own runtime orchestration, camera workflows, tracking, sessions, logging, and registry lookups; `src/api/` should own HTTP request or response handling only.
- Keep FastAPI routes thin. Route modules should validate inputs, call services, and shape responses, but they should not contain recognition logic, session decision logic, SQL, or camera-control internals.
- Keep `src/app.py` as a composition root only. It should stay focused on wiring services, runtime setup, app state, and routers rather than accumulating feature logic.
- Treat the dashboard snapshot shape as the primary UI contract. When adding new APIs or SSE payloads, make them compatible with the same conceptual data model so the frontend can normalize them cleanly.
- Keep payload schemas explicit and stable. Prefer typed schema helpers or well-defined response builders instead of ad hoc dictionaries assembled differently in multiple places.
- Normalize runtime outputs close to the service layer. Upload inference, camera latest-result, dashboard snapshot, and SSE event payloads should all be derived from shared service-level structures rather than each endpoint inventing its own shape.
- Keep session lifecycle logic separate from recognition logic. Plate detection and OCR should determine what was seen; session services should decide whether that read opens, closes, ignores, or flags a session.
- Keep storage access behind services or dedicated storage helpers. Do not scatter SQLite queries across routes, UI helpers, and unrelated runtime modules.
- Prefer dependency injection through constructors or setup functions instead of hidden globals. Shared detector, OCR engine, storage, and session services should be created in one place and passed where needed.
- Avoid monolithic service files. When a service grows too large, extract the next clear responsibility such as payload shaping, decision rules, matching logic, or repository access instead of extending one giant module. Prefer small helper methods or adjacent support modules like `session_rules.py`, `tracking_payloads.py`, `tracking_events.py`, and `tracking_quality.py` before duplicating logic inside a service.
- Keep background runtime flow explicit. Camera loops, SSE publishing, tracking updates, and logging side effects should have clear boundaries and not silently mutate unrelated application state.
- Keep configuration in YAML and settings models, not hardcoded constants. New thresholds, paths, feature flags, and provider choices should flow through `configs/` and validated settings accessors.
- Prefer contract-preserving refactors. Do not rewrite the whole runtime at once; first extract shared models, response builders, decision helpers, and repositories, then move endpoints and services over gradually.
- When adding a new backend feature, decide its home first: core algorithm, orchestration service, storage layer, or route layer. If that ownership is unclear, stop and resolve it before coding.
- If a route or service file crosses a clear readability threshold, tighten it with an extraction pass and add or update a guardrail test rather than just accepting the growth.

## Testing Guidelines

The repo includes an automated test suite under `tests/`.

Minimum checks before submitting runtime changes:

- run `python -m compileall src scripts`
- run `python -m unittest discover -s tests -p "test_*.py"`
- verify `/status`, image upload inference, and camera start or stop behavior when touching runtime code
- keep sample outputs and temporary experiments out of committed source folders

When adding new test modules, keep `test_*.py` naming.

## Current Constraints

- Current scope is centered on a single detector class: `plate_number`.
- The live pipeline selects the highest-confidence detection rather than handling multiple final plate reads per frame.
- OCR uses pretrained engines first (`PaddleOCR`, then `EasyOCR` fallback) rather than a custom recognizer.
- The current OCR dataset is prepared primarily for evaluation of pretrained OCR output; custom OCR training is optional future work rather than a current requirement.
- Config changes should be made in `configs/app_settings.yaml` or other YAML files instead of hardcoding values in the app.
- Keep recognition logic separate from session lifecycle logic; entry and exit decisions should stay in session-layer services.

## Data Handling Notes

- Empty YOLO label files are not automatically errors in this repo. Some come from Roboflow null-image negatives and are intentional.
- Before treating an empty detector label file as a missing annotation, check whether the source image belongs to that null-image set.
- OCR `true_text` values should be based on manual visual inspection of the crop when ground truth is being curated.
- Do not destroy or reshuffle the existing OCR crop split folders unless the task explicitly calls for a new split strategy.

## Entry/Exit Operating Direction

- The target deployment model remains two live cameras: one `entry` camera and one `exit` camera.
- Stable plate reads from the `entry` camera open a vehicle session.
- Stable plate reads from the `exit` camera close the most recent open session for the same plate.
- Keep debouncing and cooldown rules so repeated detections from the same car do not create duplicate entry or exit events.
- Continue using a dedicated session service and durable SQLite storage rather than embedding session state directly inside camera or OCR code.

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
