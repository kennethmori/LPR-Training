# Backend Implementation Prompt

## Purpose

This document is a standalone backend implementation prompt for the next major system stage of the USM License Plate Recognition Prototype.

Use it when you want to implement the local system foundation without mixing dashboard/UI work into the same prompt.

## Copy-Paste Prompt

```text
You are implementing the backend/system layer for the USM License Plate Recognition Prototype.

Use the current repository docs and codebase as your source of truth. Read the current implementation first, but align your changes with:
- README.md
- docs/architecture.md
- docs/CONTEXT.md
- docs/CODEX_HANDOFF.md
- docs/implementation-roadmap.md
- docs/session-flow.md
- docs/missing-pieces.md
- docs/known-issues.md
- docs/evaluation.md
- docs/ocr-curation-and-subsets.md
- docs/end-to-end-evaluation-on-traced-source-images.md

Project identity:
- Two-stage plate recognition system
- YOLO detects the plate region
- OCR reads cropped plate text
- FastAPI backend
- YAML config
- local-first thesis/demo architecture
- target workflow: `entry` and `exit` vehicle session tracking

Current implemented backend foundation:
- role-aware live recognition exists for `entry` and `exit` cameras
- still-image and video-upload inference exist
- detector + OCR + post-processing + stabilization + tracking are already wired
- session and storage services already persist events, sessions, and unmatched exits in SQLite
- the runtime currently selects one primary highest-confidence plate result per frame
- status reporting is honest when detector, OCR, or storage is unavailable
- debug logs and performance snapshots are written to JSONL

Critical backend rules you must preserve:
- keep recognition logic separate from session lifecycle logic
- do not put session business rules inside:
  - src/core/detector.py
  - src/core/ocr_engine.py
  - src/core/pipeline.py
  - src/services/camera_service.py
- keep config in YAML
- preserve one detector class: `plate_number`
- preserve one primary final result per frame unless clearly required otherwise
- preserve graceful degradation behavior
- treat SQLite as the durable source of truth
- keep the system fully usable offline

Important local-first rule:
- local recognition, session handling, and persistence must not depend on internet connectivity
- any future sync layer is optional, downstream, asynchronous, and disabled by default

Current project evidence already collected:
- OCR-only evaluation is already complete on the noisy aggregated crop set
- readable subsets at 80%, 85%, and 95% confidence were created
- a weak-confidence failure subset was created
- traced uncropped source-image sets were created
- end-to-end evaluation already shows that OCR works on readable captures, but full-image quality still depends on detector quality and capture conditions

Do not redesign the system around perfect OCR assumptions. Treat the current evaluation findings as the evidence base.

Main backend goal:
Build the local full-system backend that turns stable plate reads into durable vehicle sessions.

Target local runtime behavior:
1. An `entry` camera produces a stable recognition event.
2. The system opens a vehicle session if that plate has no open session.
3. An `exit` camera later produces a stable recognition event.
4. The system closes the most recent matching open session.
5. Repeated reads inside cooldown do not create duplicates.
6. Unmatched exits are recorded for review.

Backend implementation scope:

Phase 1: Role-aware camera architecture
- harden and extend the existing role-aware camera handling
- support camera roles:
  - `entry`
  - `exit`
- keep backward compatibility where practical
- keep `configs/app_settings.yaml` camera sources declared by role
- `camera_manager.py` already exists; extend it rather than duplicating camera orchestration logic
- support role-aware start, stop, stream, status, and latest-result behavior

Phase 2: Stable recognition event contract
- define a stable recognition event object at the boundary between recognition and session logic
- include at least:
  - `timestamp`
  - `camera_role`
  - `source_name`
  - `source_type`
  - `raw_text`
  - `cleaned_text`
  - `stable_text`
  - `plate_number`
  - `detector_confidence`
  - `ocr_confidence`
  - `ocr_engine`
  - `crop_path`
  - `annotated_frame_path`
  - `is_stable`
- only stable actionable events should reach the session layer

Phase 3: SQLite persistence
- harden and extend durable SQLite storage
- use a YAML-configured database path
- recommended path:
  - `outputs/app_data/plate_events.db`
- initialize the schema automatically
- add at least these tables:
  - `recognition_events`
  - `vehicle_sessions`
  - `unmatched_exit_events`
- keep the schema simple and explainable

Phase 4: Session service
- harden and extend `src/services/session_service.py`
- responsibilities:
  - receive stable recognition events
  - write recognition events to SQLite
  - open sessions on valid `entry` events
  - close the most recent matching open session on valid `exit` events
  - ignore duplicate repeated reads inside cooldown
  - record unmatched exits safely
- initial business rules:
  - one open session per plate at a time
  - repeated `entry` reads inside cooldown do nothing
  - repeated `exit` reads inside cooldown do nothing
  - unmatched exits are logged, not silently dropped

Phase 5: API and schemas
- keep FastAPI routes and schemas aligned with operational system state
- maintain typed Pydantic response models and reduce remaining ad hoc payload shapes
- target route surface:
  - `GET /`
  - `POST /predict/image`
  - `GET /status`
  - `POST /cameras/{role}/start`
  - `POST /cameras/{role}/stop`
  - `GET /cameras/{role}/stream`
  - `GET /cameras/{role}/latest-result`
  - `GET /sessions/active`
  - `GET /sessions/history`
  - `GET /sessions/{session_id}`
  - `GET /events/recent`
  - `GET /events/unmatched-exit`
- keep backward-compatibility wrappers for old single-camera routes only if they stay simple

Phase 6: App composition and readiness
- wire the new backend services cleanly in `src/app.py`
- preserve honest readiness reporting
- if detector weights are missing, report it clearly
- if OCR is unavailable, report it clearly
- if SQLite fails, report session-storage readiness clearly
- allow the app to start whenever practical even if some subsystems are unavailable

Implementation constraints:
- inspect the current repo structure before editing
- preserve the current working recognition flow while extending it
- do not reshuffle or destroy datasets
- do not overwrite evaluation artifacts unless rerunning them is explicitly required
- do not hardcode absolute paths
- do not add internet-dependent behavior into the critical path
- do not couple session logic to detector/OCR internals
- do not overengineer the first persistence layer

Recommended backend files to inspect and likely update:
- configs/app_settings.yaml
- src/app.py
- src/core/pipeline.py
- src/services/result_service.py
- src/services/camera_service.py
- src/api/routes.py
- src/api/schemas.py

Likely backend modules to extend:
- src/services/session_service.py
- src/services/storage_service.py
- src/services/camera_manager.py

Backend verification requirements:
- verify syntax / import sanity
- verify `/status`
- verify still-image inference still works
- verify camera start and stop behavior
- verify role-aware camera handling
- verify session open on valid `entry`
- verify session close on valid `exit`
- verify duplicate prevention behavior
- verify unmatched exit behavior
- verify honest failure behavior when OCR, detector, camera, or DB is unavailable

Backend deliverables:
1. YAML config updates for role-aware cameras and session settings
2. backend code changes implementing the local full-system foundation
3. SQLite-backed event and session persistence
4. session service with duplicate prevention and unmatched-exit handling
5. route and schema updates for events and sessions
6. a short summary of:
   - what was implemented
   - what assumptions were made
   - what remains for later
   - what should be tested next

Important mindset:
- optimize for a solid, understandable, local-first thesis/demo system
- prioritize maintainability and separation of responsibilities
- implement the simplest correct backend architecture that matches the documented plan
```

## Suggested Use

Use this file when the task is mainly:

- system architecture
- FastAPI routes
- camera roles
- stable event modeling
- SQLite
- session logic
