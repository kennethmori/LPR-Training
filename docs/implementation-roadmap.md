# Implementation Roadmap

## Purpose

This document turns the current codebase status into a practical next-step plan.

It answers:

- what is already done
- what should be improved next
- what can wait until later
- what counts as a strong thesis-demo milestone from the current baseline

The project has already moved past a recognition-only prototype. The roadmap now focuses on hardening the existing local-first session-tracking system.

## Current Status

The repository already includes these foundations:

- YOLO detector integration for one class: `plate_number`
- OCR integration with pretrained engines
- post-processing and short-history stabilization
- image upload inference
- video upload inference
- role-aware live camera inference through `entry` and `exit` cameras
- FastAPI-based dashboard and API routes
- SQLite-backed recognition-event and vehicle-session persistence
- unmatched-exit handling, moderation routes, and performance snapshots
- automated tests for detector, pipeline, session, tracking, registry, and key API settings/session routes
- prepared OCR evaluation data and detector dataset splits

Current data snapshot in the workspace:

- detector dataset in `data/images/{train,val,test}` and `data/labels/{train,val,test}`
- OCR split datasets in `data/ocr/train_crops`, `data/ocr/val_crops`, and `data/ocr/test_crops`
- aggregated OCR evaluation set in `data/ocr/all_crops` with `data/ocr/all_labels.csv`

What this means in practice:

- the local app already supports the main entry and exit demo flow
- the main missing work is around verification, maintainability, and operational maturity
- recognition quality work can continue in parallel with app hardening

## Main Project Goal

The larger target is still a clear campus vehicle monitoring workflow where:

1. an `entry` camera recognizes a stable plate
2. the system opens a vehicle session
3. an `exit` camera recognizes that same plate later
4. the system closes the matching session

That core flow is already present in the current codebase. The next milestone is making that flow more reliable, testable, and easier to operate.

## Recommended Priority Order

The best next-stage order for this repository is:

1. Expand automated coverage for long-running camera loops, video uploads, and end-to-end dual-role flows
2. Tighten API response typing and schema alignment
3. Add database lifecycle support such as migrations or versioning
4. Improve moderation and operator-facing workflows
5. Continue detector and OCR quality improvements
6. Harden real two-camera deployment behavior
7. Only then consider optional sync or remote dashboard work

This order keeps local reliability first and avoids turning optional online work into a new critical-path dependency.

## Phase 1: Verification And Test Coverage

This phase is about proving that the existing behavior is correct and stable.

### Goals

- make session decisions verifiable
- reduce regression risk when tuning thresholds or routes
- give future changes a safety net

### Tasks

- expand `SessionService` and storage-focused tests for edge cases (cooldown, near-match ambiguity, unmatched exits)
- add integration-style tests for camera start or stop behavior and role switching with mocked sources
- extend API tests for video upload, moderation, and settings failure paths
- keep reusable fixtures for realistic `entry` then `exit` sequences and negative variants

### Deliverables

- broader `tests/` coverage across service and API integration paths
- documented repeatable test command for local runs and CI: `python -m unittest discover -s tests -p "test_*.py"`
- a short verification checklist that combines automated checks and targeted manual runtime checks

## Phase 2: API And Config Hardening

This phase is about making the runtime contract clearer and easier to maintain.

### Goals

- keep route responses aligned with declared schemas
- reduce ambiguity in operator-facing and integration-facing payloads
- make configuration behavior easier to reason about

### Tasks

- audit endpoints that still build ad hoc dict payloads
- return schema-aligned payloads consistently where practical
- document role-based camera configuration and detector backend selection more clearly
- review threshold defaults in `configs/app_settings.yaml`

### Deliverables

- cleaner API contracts
- fewer docs-versus-code mismatches
- better confidence when changing settings or UI consumers

## Phase 3: Database Lifecycle And Moderation

This phase is about making the SQLite layer easier to evolve safely.

### Goals

- prepare for schema evolution
- improve operator review workflows
- keep local data durable and understandable

### Tasks

- introduce a migration or versioning strategy
- define backup and retention expectations for longer-running deployments
- improve unmatched-exit review and manual moderation workflows if needed
- document what operational data is authoritative in SQLite versus debug-only in JSONL

### Deliverables

- database lifecycle guidance
- safer future schema changes
- clearer operator-facing moderation expectations

## Phase 4: Recognition Quality Improvements

This phase is about improving read quality without destabilizing the system layer.

### Goals

- improve difficult real-world plate reads
- tune thresholds using the prepared evaluation assets
- keep detector-only, OCR-only, and end-to-end results separate

### Tasks

- continue detector fine-tuning and threshold evaluation
- evaluate OCR quality on the prepared crop truth files
- analyze failure cases in low-light, blur, and near-match scenarios
- decide whether multi-detection support is worth the added complexity later

### Deliverables

- updated detector and OCR metrics
- concrete notes on failure modes and threshold tradeoffs
- better confidence in real deployment conditions

## Phase 5: Deployment Hardening

This phase is about making the app easier to run in a real two-camera setup.

### Goals

- keep the local app stable during long-running camera sessions
- make operator workflows less fragile
- preserve graceful degradation

### Tasks

- test with realistic dual-camera traffic sequences
- refine startup, shutdown, and failure messaging
- validate upload limits, camera source settings, and detector backend switching
- add runbook-style deployment notes for a campus workstation setup

### Deliverables

- more predictable field behavior
- clearer recovery steps when a camera or dependency is unavailable
- stronger demo readiness

## Phase 6: Optional Online Layer

This phase is explicitly optional and comes after the local system is solid.

### Goals

- expose selected results remotely without weakening the local critical path

### Tasks

- add a background sync worker only if the user wants it
- mark synced versus unsynced records locally
- keep sync non-blocking and internet-optional
- build or connect a remote dashboard only as a downstream reporting layer

### Deliverables

- optional remote visibility
- preserved local-first reliability

## Definition Of A Strong Next Milestone

The next milestone should be considered successful when all of these are true:

- session open, close, duplicate-ignore, and unmatched-exit behavior are covered by tests
- the main API endpoints return predictable schema-aligned payloads
- the SQLite lifecycle is documented clearly enough for future changes
- the app still degrades honestly when detector, OCR, storage, or camera inputs are unavailable
- detector and OCR quality work can continue without muddying the operational layer

## What Can Wait

These are useful, but they should not block the next milestone:

- a heavy frontend rewrite
- remote-first architecture
- cloud dependencies in the live recognition loop
- multi-plate final decision logic in one frame
- custom OCR training as a required runtime dependency

The strongest immediate path is to keep the current local system honest, tested, and stable.
