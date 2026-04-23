# Entry and Exit Session Flow

## Goal

The target system behavior is not only to recognize plate numbers, but also to manage a visit session for each vehicle entering and leaving campus.

Desired behavior:

1. The entry camera recognizes a plate number.
2. The system opens a session for that plate.
3. The exit camera recognizes the same plate number later.
4. The system closes the session.

## Current State

The current codebase can:

- detect a plate from an image or live camera frame
- read plate text with OCR
- stabilize plate text across recent frames
- run separate `entry` and `exit` camera roles
- create and close persistent vehicle sessions in SQLite
- match stable exit detections to the latest open session for the same plate
- record unmatched exit events for operator review

Remaining gaps are mostly around test coverage, API contract strictness, and operational hardening.

## Current Runtime Mapping

The refactored codebase now maps the session flow to concrete modules:

- `src/core/pipeline.py` produces normalized recognition payloads.
- `src/services/tracking_service.py` manages live camera track selection and selective OCR.
- `src/runtime.py` enriches camera payloads with vehicle lookup and session decisions.
- `src/services/session_service.py` applies duplicate, ambiguity, and open/close rules.
- `src/storage/event_repository.py` and `src/storage/session_repository.py` persist the durable event and session records.

That means entry and exit lifecycle logic remains above recognition and below the API, which is the intended boundary.

## Recommended Architecture

Keep the system split into two layers:

### 1. Recognition Layer

This layer already mostly exists.

Responsibilities:

- detect the plate location
- crop the plate
- run OCR
- clean the OCR text
- stabilize the result

The output of this layer should be a stable recognition event such as:

- `camera_role`
- `plate_number`
- `timestamp`
- `confidence`
- optional image or crop reference

### 2. Session Layer

This layer is already implemented and should remain separate from recognition logic.

Responsibilities:

- receive stable recognition events
- decide whether to open a new session
- decide whether to close an existing session
- prevent duplicate events from repeated frames
- store active and completed sessions

This separation is important because plate recognition and visit tracking solve different problems.

## Camera Roles

The target setup uses two cameras:

- `entry`
- `exit`

Each recognition event should carry the camera role so the session logic knows how to handle it.

## Session Lifecycle

### Entry Event

When the `entry` camera produces a stable plate number:

- check whether the plate already has an open session
- if no open session exists, create one
- if an open session already exists, ignore the duplicate or update a last-seen timestamp depending on policy

### Exit Event

When the `exit` camera produces a stable plate number:

- look up the most recent open session for that plate
- if one exists, set the exit time and close the session
- if none exists, record an unmatched exit event for review

## Suggested Session Fields

Each session record should include at least:

- `plate_number`
- `entry_time`
- `exit_time`
- `entry_camera`
- `exit_camera`
- `status`

Helpful optional fields:

- `entry_confidence`
- `exit_confidence`
- `entry_snapshot_path`
- `exit_snapshot_path`
- `notes`

## Duplicate Prevention

Live video sees the same car across many frames, so session logic needs debouncing rules.

Recommended rules:

- require a stable OCR result before creating an event
- ignore repeated detections of the same plate from the same camera within a cooldown window
- allow only one open session per plate unless the project explicitly supports re-entry overlap

## Suggested Storage

A durable session store is already in use.

Current store:

- SQLite

Why:

- simple local setup
- no external server required
- enough for a prototype or thesis demo

## Example Flow

1. Entry camera recognizes `ABC1234`.
2. The result stabilizes across recent frames.
3. The system opens a session for `ABC1234` with status `open`.
4. Later, the exit camera recognizes `ABC1234`.
5. The result stabilizes again.
6. The system finds the open `ABC1234` session and marks it `closed`.

## Implementation Direction

Current implementation includes:

- a session service in `src/services/session_service.py`
- a SQLite persistence layer in `src/services/storage_service.py`
- role-aware cameras managed through `entry` and `exit` services
- API routes for active sessions, history, events, unmatched exits, and moderation

Recommended next improvements:

- expand tests for session and storage edge cases
- tighten schema-first API response enforcement
- add migration/versioning support for long-lived SQLite deployments

Recognition should remain focused on reading plates. Session logic should sit above it rather than inside the OCR pipeline itself.
