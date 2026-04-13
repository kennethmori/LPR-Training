# Implementation Roadmap

## Purpose

This document turns the current prototype status into a practical build plan.

It answers:

- what is already done
- what should be built next
- what can wait until later
- what counts as a good thesis-demo or prototype milestone

The goal is to move from a recognition prototype into a usable campus vehicle monitoring workflow without mixing priorities.

## Current Status

The repository already has a working recognition prototype with these foundations:

- YOLO detector integration for one class: `plate_number`
- OCR integration with pretrained engines
- post-processing and short-history stabilization
- image upload and live camera inference
- FastAPI-based web UI
- prepared OCR evaluation data

Current data snapshot in the workspace:

- detector dataset in `data/images/{train,val,test}` and `data/labels/{train,val,test}`
- OCR split datasets in `data/ocr/train_crops`, `data/ocr/val_crops`, and `data/ocr/test_crops`
- aggregated OCR evaluation set in `data/ocr/all_crops` with `data/ocr/all_labels.csv`

What this means in practice:

- OCR evaluation can already be run from the prepared crop truth files
- detector fine-tuning can proceed once the team is satisfied with the detector labels and fine-tuning settings
- the main missing work is the system layer above recognition

## Main Project Goal

The larger target is not only reading plate numbers.

The real target is a campus vehicle monitoring system where:

1. an `entry` camera recognizes a stable plate
2. the system opens a vehicle session
3. an `exit` camera recognizes that same plate later
4. the system closes the matching session

That means the next steps should prioritize turning recognition output into reliable, trackable events.

## Recommended Priority Order

The best next-stage order for this repository is:

1. Finish detector fine-tuning and detector-only validation
2. Evaluate OCR on the prepared crop truth data
3. Evaluate the full detector-plus-OCR pipeline
4. Add camera roles for `entry` and `exit`
5. Add a session service above the recognition layer
6. Add persistent storage for active and completed sessions
7. Extend API routes and UI for operational monitoring
8. Add tests, logging improvements, and deployment hardening

This order keeps the model quality questions separate from the application workflow questions.

## Phase 1: Recognition Readiness

This phase is about proving that the recognition pipeline is good enough to build on.

For the detailed working plan, see [phase-1-plan.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/phase-1-plan.md).

### Detector Work

Goals:

- train `yolo26s.pt` using the current detector dataset
- validate detector performance on `val`
- measure final detector behavior on `test`

Tasks:

- run detector fine-tuning with `scripts/train_detector.py`
- export validation metrics and confusion information from Ultralytics results
- inspect detector failure cases manually
- confirm that empty YOLO labels that came from Roboflow null-image negatives are intentional

Deliverables:

- trained detector weights in `models/detector/best.pt`
- saved training results and plots
- a short detector evaluation summary for the thesis or project report

### OCR Work

Goals:

- measure how well the current pretrained OCR setup performs on the prepared crops

Tasks:

- run OCR inference over `val_crops` and `test_crops`
- save predictions as CSV with `image_path,predicted_text`
- compare predictions against ground truth using `scripts/evaluate_ocr.py`
- analyze common OCR failure patterns

Deliverables:

- OCR prediction CSVs
- exact-match and character-accuracy metrics
- a short error analysis summary

### End-to-End Recognition Work

Goals:

- measure realistic pipeline quality when detector and OCR run together

Tasks:

- run the full recognition pipeline on a held-out evaluation set
- save detector-plus-OCR outputs into an evaluation CSV
- score the results with `scripts/evaluate_end_to_end.py`

Deliverables:

- end-to-end evaluation CSV
- end-to-end exact match accuracy
- detection rate and runtime summary

## Phase 2: Entry and Exit Architecture

This phase starts the actual campus monitoring system design.

### Camera Roles

The codebase currently assumes one camera source.

Next work:

- support two logical camera roles: `entry` and `exit`
- allow camera-specific configuration
- make camera outputs and logs carry their role explicitly

Expected implementation direction:

- update config structure in `configs/app_settings.yaml`
- extend camera service or introduce a camera manager
- ensure every recognition event includes `camera_role`

### Recognition Event Layer

Before session tracking is added, the app should expose a cleaner event abstraction.

Each event should include at least:

- `plate_number`
- `camera_role`
- `timestamp`
- `raw_text`
- `cleaned_text`
- `stable_text`
- `detector_confidence`
- `ocr_confidence` when available
- optional snapshot or crop reference

This event object becomes the boundary between recognition code and session code.

## Phase 3: Session Tracking

This phase turns recognition into a visit-monitoring workflow.

### Session Service

Add a dedicated service, likely in `src/services/session_service.py`.

Responsibilities:

- accept stable recognition events
- open sessions for valid entry events
- close sessions for matching exit events
- keep the matching logic out of detector and OCR modules

### Session Rules

The initial business rules should stay simple and explicit:

- one open session per plate at a time
- `entry` event opens a session if none is open
- repeated `entry` reads during cooldown do not open duplicates
- `exit` event closes the most recent open session for that plate
- unmatched exits are logged for review

### Suggested Session Fields

Store at least:

- `plate_number`
- `entry_time`
- `exit_time`
- `entry_camera`
- `exit_camera`
- `status`

Helpful extras:

- `entry_snapshot_path`
- `exit_snapshot_path`
- `entry_confidence`
- `exit_confidence`
- `notes`

## Phase 4: Persistence

The current app does not yet have durable session storage.

Recommended first step:

- SQLite

Why SQLite is the right starting point:

- simple to set up locally
- good fit for a prototype or thesis demo
- enough for active sessions, completed sessions, and event logs

Suggested persistence scope:

- active sessions
- completed sessions
- unmatched exit events
- optionally, raw recognition event logs

## Phase 5: API And UI Expansion

Once sessions exist, the frontend and API need to reflect that new system layer.

### API Additions

Recommended new endpoints:

- `GET /sessions/active`
- `GET /sessions/history`
- `GET /events/recent`
- `GET /events/unmatched-exit`
- `POST /sessions/{id}/close` for controlled manual override if needed

Also recommended:

- make route outputs align more consistently with `src/api/schemas.py`
- move away from mostly plain dict responses over time

### UI Additions

Recommended UI capabilities:

- side-by-side `entry` and `exit` camera panels
- active vehicles currently inside campus
- completed visit history
- recent recognition events
- unmatched or suspicious event review

Optional but useful later:

- manual correction of a plate event
- manual force-close of a session
- filters by date, plate number, or status

## Phase 6: Reliability And Engineering Work

This phase focuses on turning the prototype into something more stable and maintainable.

### Testing

The repo still needs a proper testing layer.

Recommended additions:

- unit tests for post-processing rules
- unit tests for result stabilization behavior
- unit tests for session open and close rules
- integration tests for recognition-event to session flow

### Logging And Debugging

Recommended improvements:

- clearer event logs by camera role
- explicit unmatched-exit logging
- structured logging around session state changes
- optional failure-case image export for hard samples

### Configuration Hygiene

Recommended additions:

- session cooldown settings in YAML
- camera-role settings in YAML
- database path setting in YAML
- runtime toggles for debug exports

## Phase 7: Deployment And Demo Readiness

This phase is about making the system usable in a real demonstration.

Recommended tasks:

- define the actual two-camera deployment setup
- test with realistic entry and exit traffic sequences
- validate performance under day and night conditions
- verify recovery behavior after app restart
- prepare screenshots, metrics, and workflow diagrams for reporting

## Practical Milestones

The following milestones are realistic and useful.

### Milestone A: Recognition Baseline

Definition:

- detector trained
- OCR evaluated
- end-to-end metrics collected

### Milestone B: Dual-Camera Prototype

Definition:

- app understands `entry` and `exit` roles
- both sources can be monitored
- stable recognition events include camera role

### Milestone C: Session Prototype

Definition:

- entry opens a session
- exit closes the matching session
- duplicate reads are filtered with cooldown

### Milestone D: Usable Thesis Demo

Definition:

- dual-camera workflow works end to end
- sessions survive restart through SQLite
- UI shows active sessions and recent history
- evaluation metrics and demo evidence are documented

## Definition Of Done For The Next Major Stage

The next major stage should be considered complete when all of these are true:

- detector metrics are documented
- OCR metrics are documented
- end-to-end metrics are documented
- the app supports `entry` and `exit` camera roles
- stable recognition events feed into a dedicated session service
- session records are stored durably
- duplicate entry and exit events are controlled
- the UI exposes active and completed sessions

## Risks And Watchouts

The main risks in the next stage are:

- OCR misreads causing wrong session matches
- repeated detections causing duplicate sessions
- camera-role logic being mixed directly into OCR or detector code
- unclear source of truth between recognition events and session records
- overcomplicating the system before baseline metrics are collected

The safest design choice is to keep layers separate:

- recognition layer reads plates
- session layer decides what the event means operationally
- persistence layer stores the result

## Suggested Immediate Next Step

If the team wants the best next action right now, it should be:

1. train and validate the detector
2. run OCR evaluation on the prepared crop truth files
3. collect end-to-end metrics
4. only then begin the session-service implementation

That sequence gives the project a stronger foundation and cleaner reporting.
