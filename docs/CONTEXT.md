# Project Context

## What This Project Is About

This project is a two-stage license plate recognition system for the University of Southern Mindanao. The first stage uses YOLO to detect the license plate region, and the second stage uses OCR to read the cropped plate text.

The current app is a local-first FastAPI prototype that already includes session tracking on top of the recognition pipeline.

## Current Scope

- one detector class: `plate_number`
- one primary plate result per frame
- image upload inference
- video upload inference
- live camera inference
- role-aware `entry` and `exit` camera support through a camera manager
- pretrained OCR first, with fallback support
- conservative post-processing and result stabilization
- SQLite-backed recognition-event and vehicle-session persistence
- session tracking with cooldown, duplicate suppression, and unmatched-exit logging
- performance snapshots and honest readiness reporting when detector, OCR, or storage is unavailable

## Implemented Entry And Exit System

The current runtime already supports the main campus-monitoring flow:

- an `entry` camera can recognize a stable plate number
- the system can open a vehicle session for that plate
- an `exit` camera can recognize the same plate later
- the system can close the most recent matching open session
- unmatched exits are recorded for review

Key rules currently enforced by the app:

- keep recognition logic separate from session lifecycle logic
- use stable recognition events, not raw frame-by-frame OCR output
- apply confidence and stability thresholds before a session decision is made
- apply cooldown and duplicate suppression rules per plate and camera role
- persist operational state in SQLite while keeping JSONL logs for debugging

## Main Remaining Gaps

The largest missing pieces are now around hardening rather than first-time implementation:

1. Expanded automated coverage for long-running camera loops, video uploads, and end-to-end entry/exit scenarios
2. Stricter schema-first API response handling for remaining ad hoc route payloads
3. Database lifecycle support such as migrations or versioning
4. Better moderation and deployment workflows for real operator use
5. Continued detector and OCR quality improvements for hard cases
6. Optional future sync or online dashboard work, kept separate from the local critical path

## Suggested Next Build Order

1. Expand test coverage for camera runtime edge cases, upload flows, and entry/exit lifecycle regressions.
2. Tighten response modeling so returned payloads consistently align with schemas.
3. Add database migration or versioning support.
4. Improve moderation, review, and operational runbooks.
5. Keep iterating on detector and OCR quality with the prepared evaluation assets.
6. Only after the local system is stable, consider optional background sync or remote dashboards.

## Data And Evaluation Plans

The project still keeps model training, data preparation, and runtime behavior as separate concerns:

- prepare raw media, manifests, and annotation folders
- fine-tune the detector in Colab with YOLO when needed
- validate detector-only, OCR-only, and end-to-end performance separately
- keep local runtime results separate from Colab training metrics
- use OCR crop datasets with ground-truth labels for evaluation

## Main Idea In One Line

This project is now a local-first license plate recognition system with entry and exit session tracking, and the next work is mostly about expanding coverage, hardening operations, and improving accuracy.
