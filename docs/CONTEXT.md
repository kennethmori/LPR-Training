# Project Context

## What This Project Is About

This project is a two-stage license plate recognition prototype for the University of Southern Mindanao. The first stage uses YOLO to detect the license plate region, and the second stage uses OCR to read the cropped plate text.

The current prototype is focused on reliable recognition, clear status reporting, and a simple FastAPI-based web UI.

## Current Scope

- one detector class: `plate_number`
- one primary plate result per frame
- image upload inference
- live webcam inference
- pretrained OCR first, with fallback support
- conservative post-processing and result stabilization
- honest status reporting when detector weights or OCR dependencies are missing

## Planned Entry and Exit System

The intended next phase is not just recognition, but campus vehicle session tracking.

Target behavior:

- an `entry` camera recognizes a stable plate number
- the system opens a vehicle session for that plate
- an `exit` camera recognizes the same plate later
- the system closes the matching open session

Key rules:

- keep recognition logic separate from session lifecycle logic
- use stable recognition events, not raw frame-by-frame OCR output
- add debouncing and cooldown rules to prevent duplicate events
- prefer a dedicated session service and SQLite-backed persistence

## Missing Pieces To Build Next

The docs consistently identify these as the major remaining parts:

1. Dual-camera support with `entry` and `exit` roles
2. A session service that opens and closes vehicle visits
3. Durable storage for active and completed sessions
4. Duplicate-prevention and plate-matching rules
5. API routes for sessions and events
6. UI updates for entry, exit, and session monitoring

## Suggested Build Order

1. Add camera roles and dual-camera support.
2. Add a session service.
3. Add SQLite persistence for session records.
4. Add cooldown and matching rules.
5. Add API endpoints for sessions and events.
6. Update the frontend for operational monitoring.
7. Add tests and verification workflows.

## Data And Evaluation Plans

The project also plans separate handling for model training, data preparation, and evaluation:

- prepare raw media, manifests, and annotation folders
- fine-tune the detector in Colab with YOLO
- validate detector-only, OCR-only, and end-to-end performance separately
- keep local runtime results separate from Colab training metrics
- use OCR crop datasets with ground-truth labels for evaluation

## Main Idea In One Line

The project starts as a license plate recognition prototype and is meant to evolve into a campus vehicle monitoring system with entry and exit session tracking.
