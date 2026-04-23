# Missing Pieces

## Purpose

This document tracks what is still missing after the current dual-camera and session-tracking implementation.

The repository now includes:

- role-aware camera services (`entry` and `exit`)
- session lifecycle handling (`open`, `close`, unmatched exits)
- SQLite-backed persistence for events and sessions
- UI/API surfaces for active sessions, history, recent events, and unmatched exits

## Remaining Gaps

### 1. Test Coverage Expansion

A formal automated test suite now exists under `tests/`.

Remaining work:

- broaden integration coverage for long-running camera loops and role-based stream behavior
- add more end-to-end regression scenarios for entry, exit, duplicate suppression, and unmatched exits
- extend upload and moderation-path testing for larger payloads and error handling cases

### 2. API Contract Strictness

Pydantic schemas cover most API data endpoints, but some handlers still return ad hoc dictionaries or custom JSON responses.

Missing work:

- enforce schema-first serialization on all route responses
- add stronger response validation in integration tests

### 3. Database Lifecycle Management

SQLite schema initialization is currently code-driven and immediate.

Missing work:

- schema versioning/migrations for future changes
- backup/retention strategy for long-running deployments

### 4. Operational Hardening

Core behavior is present, but production-style safeguards can still improve.

Missing or incomplete work:

- richer auth/authorization if deployed beyond local operator use
- clearer moderation/audit workflows for reviewed or corrected events
- deployment runbooks for real two-camera campus environments

### 5. Recognition Quality Expansion

The architecture supports sessions, but recognition quality is still model-dependent.

Missing or ongoing work:

- better detector/OCR performance in low-light and motion blur
- optional multi-detection handling beyond single best box per frame
- continued dataset curation for difficult plate cases

## Summary

The platform has moved past prototype-only recognition and now includes operational session tracking plus baseline automated tests. The main missing pieces are broader integration coverage, stricter API contracts, and longer-term operational maturity.
