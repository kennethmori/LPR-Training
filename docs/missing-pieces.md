# Missing Pieces

## Purpose

This document tracks the major project pieces that are still missing relative to the target campus entry and exit system.

The current repository already performs plate detection and OCR. The remaining work is mostly about turning recognition into a reliable operational system with sessions, persistence, and monitoring.

## Highest-Priority Missing Pieces

These are the most important missing parts for the next implementation phase:

1. Dual-camera entry and exit architecture
2. Session service for opening and closing vehicle visits
3. Durable storage for session records
4. Duplicate-prevention and plate-matching rules
5. UI and API support for active and completed sessions

## Core Feature Gaps

### Dual-Camera Support

The current live system is built around a single camera source.

Missing work:

- separate `entry` and `exit` camera roles
- camera-specific configuration
- support for running or monitoring both streams together

### Session Tracking

The repo does not yet create vehicle sessions.

Missing work:

- open a session when a stable plate is recognized at entry
- close the matching open session when the same plate is recognized at exit
- track session status such as `open` and `closed`

### Persistent Storage

There is no durable session database yet.

Missing work:

- store active and completed sessions
- store timestamps and camera roles
- preserve records across app restarts

Recommended first step:

- SQLite

## Recognition Pipeline Gaps

The recognition layer exists, but it still has important operational limitations.

Missing or incomplete work:

- support beyond the single highest-confidence detection per frame
- cooldown rules for repeated detections of the same vehicle
- handling for unmatched exit events
- handling for repeated entries or OCR misreads
- stronger reliability under low light, motion blur, and angled plates

The current stabilization service helps reduce OCR flicker, but it is not a session manager.

## Backend and API Gaps

The backend still needs a session-oriented layer on top of recognition.

Missing work:

- `session_service.py` or equivalent
- a persistence layer for session records
- routes for active sessions
- routes for completed sessions
- routes for recent entry and exit events
- clearer typed response models in the API layer

## UI Gaps

The current UI is a recognition dashboard, not yet a campus traffic or guardhouse dashboard.

Missing work:

- side-by-side entry and exit camera feeds
- active vehicles currently inside campus
- completed visit history
- unmatched or suspicious events
- possible manual correction or override actions

## Data and Model Gaps

The app architecture is only part of the project. Model quality still matters.

Missing or ongoing work:

- strong detector weights in `models/detector/best.pt`
- OCR evaluation on actual campus plate samples
- better coverage for difficult image conditions
- a more unified reporting workflow for detector, OCR, and end-to-end metrics

## Engineering Gaps

There are also software engineering tasks still missing before this becomes a more complete system.

Missing work:

- automated tests
- database schema management or migrations
- a deployment approach for a real two-camera setup
- user roles, admin review, or audit trail if the system becomes operational

## Practical Build Order

Recommended order for the next stage:

1. Add camera roles and dual-camera support.
2. Add a session service.
3. Add SQLite-backed persistence.
4. Add duplicate-prevention and matching rules.
5. Add API endpoints for sessions and events.
6. Update the frontend for entry, exit, and session monitoring.
7. Add tests and verification workflows.

## Summary

The current project already recognizes plate numbers.

What is still missing is the system layer that answers questions like:

- who entered
- who has not exited yet
- when a vehicle left
- whether an exit matches an earlier entry

That next layer is what turns this from a recognition prototype into a usable campus vehicle monitoring system.
