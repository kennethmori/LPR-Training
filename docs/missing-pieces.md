# Missing Pieces

## Purpose

This document tracks what is still missing after the current dual-camera and session-tracking implementation.

The repository now includes:

- role-aware camera services (`entry` and `exit`)
- session lifecycle handling (`open`, `close`, unmatched exits)
- SQLite-backed persistence for events and sessions
- UI/API surfaces for active sessions, history, recent events, and unmatched exits

## Remaining Gaps

### 1. Automated Testing

There is still no formal automated test suite.

Missing work:

- unit tests for `SessionService` decision rules
- storage tests for CRUD and moderation flows
- API tests for camera/session/event endpoints

### 2. API Contract Strictness

Pydantic schemas exist, but route handlers still mostly build plain dictionaries.

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

The platform has moved past prototype-only recognition and now includes operational session tracking. The main missing pieces are test coverage, stricter API contracts, and longer-term operational maturity.
