# Vehicle Registration And Profile Linking

This document explains the vehicle registration and profile-linking feature that was added on top of the existing USM gate LPR pipeline.

It is intended as agent and developer context, not as end-user documentation.

## Goal

The system should not stop at reading a plate number.

After a stable plate is recognized, the app should try to match that plate against a vehicle registration registry and show a guard-facing profile summary.

This feature extends the current pipeline:

1. detector finds the plate
2. OCR reads the text
3. stabilization confirms a usable plate read
4. session logic opens or closes gate sessions
5. registry lookup enriches the result with vehicle profile context

The recognition and session flow still stays intact. The registry layer is additive.

## Design Rule

Do not use `plate_number` as the true internal primary key.

Use `vehicle_id` as the durable internal identifier for registered vehicles.

Why:

- OCR can misread a plate
- a plate can be corrected later
- a vehicle record may need edits without changing internal identity

`plate_number` is the main lookup key used by the LPR flow, but not the true record identity.

## Current Implementation Summary

The current implementation adds:

- registry tables in SQLite
- seeded dummy vehicle profiles bound to real high-confidence recognized plates
- a registry lookup service
- payload enrichment for recognition results
- dashboard display of matched profile state
- API lookup endpoints for agents or frontend use

The current implementation does not yet add:

- admin CRUD pages for vehicle registration
- real document file upload workflows
- manual approval or renewal actions in the UI
- fuzzy auto-matching between OCR near-misses and registry plates

## Main Files

- `src/services/storage_service.py`
  Adds registry tables, migration-style column checks, and dummy profile seeding.
- `src/services/vehicle_registry_service.py`
  Owns plate lookup, status interpretation, document summaries, and recent history shaping.
- `src/app.py`
  Wires the registry service into the main app lifecycle and camera payload handling.
- `src/api/schemas.py`
  Adds profile, document, history, and lookup response models.
- `src/api/routes.py`
  Adds registry lookup routes and attaches lookup data to upload results.
- `templates/index.html`
  Adds a vehicle profile section to the recognition panel.
- `static/js/app.js`
  Renders registration status, owner summary, document summaries, and recent gate history.
- `static/css/style.css`
  Styles the new profile summary section.
- `configs/app_settings.yaml`
  Adds `vehicle_registry` settings.

## Data Model

### `registered_vehicles`

Current purpose:

- one row per vehicle profile

Key fields:

- `vehicle_id`
- `plate_number`
- `owner_name`
- `user_category`
- `owner_affiliation`
- `owner_reference`
- `vehicle_type`
- `vehicle_brand`
- `vehicle_model`
- `vehicle_color`
- `registration_status`
- `approval_date`
- `expiry_date`
- `status_notes`
- `record_source`

### `vehicle_documents`

Current purpose:

- stores document metadata tied to a registered vehicle

Key fields:

- `document_id`
- `vehicle_id`
- `document_type`
- `document_reference`
- `file_ref`
- `verification_status`
- `verified_at`
- `expires_at`
- `notes`

Important note:

The current implementation stores dummy document metadata only. It does not yet support real file upload or secure file serving.

### Extended existing tables

`recognition_events` now also stores:

- `matched_vehicle_id`
- `matched_registration_status`
- `manual_verification_required`

`vehicle_sessions` now also stores:

- `matched_vehicle_id`
- `matched_registration_status`

This lets session history and event history keep some registry context after a lookup.

## Lookup Rules

The registry service currently uses exact normalized plate matching only.

Current outcomes:

- `approved`
  Registered and normal gate handling can continue.
- `pending`
  Record exists, but it is not cleared for normal approved handling.
- `expired`
  Record exists, but it is expired and should be flagged.
- `blocked`
  Record exists, but it should be clearly flagged for guard intervention.
- `visitor_unregistered`
  No record matched the recognized plate.

Guard-facing rule:

If no match exists, the vehicle is shown as `visitor/unregistered` and `manual_verification_required = true`.

It is not treated as an approved visitor.

## Dummy Seed Behavior

The current registry bootstrap is intentionally dummy-data-first.

When `StorageService` initializes and:

- the registry tables are empty
- auto-seeding is enabled

it looks at existing `recognition_events` and selects up to 5 viable plates with:

- `ocr_confidence >= 0.90`
- non-empty `plate_number`
- alphanumeric plate shape
- not obvious placeholder reads like `ENTRY`, `EXIT`, or `NOW`

It then creates dummy vehicle profiles tied to those real recognized plates.

This keeps the feature demoable even before the admin registration workflow exists.

## Current Seeded Profiles In This Workspace

In the checked local workspace on April 20, 2026, the current `outputs/app_data/plate_events.db` seeded these sample profiles:

- `MBF1028` -> student -> approved
- `MAN5467` -> staff -> approved
- `HAN5467` -> faculty -> pending
- `KBH4894` -> contractor -> expired
- `HAU567` -> alumni -> blocked

These are dummy people and dummy document metadata.

The plate numbers were chosen from real high-confidence recognition data already stored in the local database.

Important:

If a fresh database is created from different recognition history, the exact seeded plates may differ because the seed list is derived from whatever qualifying high-confidence events exist at initialization time.

## Current API Surface

Current read endpoints:

- `GET /vehicles/lookup?plate_number=...`
  Returns a guard-facing lookup payload for a plate.
- `GET /vehicles/{vehicle_id}`
  Returns the current vehicle profile.

The dashboard also receives `vehicle_lookup` inside live recognition payloads.

## Dashboard Behavior

The right-side recognition panel now shows:

- detected plate
- matched or unmatched registry badge
- owner name or visitor fallback
- category and affiliation summary
- vehicle summary
- registry status
- whether manual verification is required
- document verification summary
- recent gate history for that plate

This is currently read-only operator context.

## Status Interpretation Notes

Current status handling is intentionally conservative.

- `approved` means matched and usable
- `pending`, `expired`, and `blocked` all remain visible as matched records, but they still require guard awareness
- `visitor_unregistered` means there is no matching profile

The registry layer does not block session creation by itself.

The current system still logs recognition and session behavior. The registry result is an operational context layer shown to guards and APIs.

## What Is Still Dummy

These parts are still placeholders:

- owner identities
- owner references
- document references
- `file_ref` values such as `dummy://vehicle_documents/...`
- seeded profile composition

This is intentional for now.

The current goal is to make the profile-linking architecture real before building the full registration workflow.

## Recommended Next Steps

When continuing this feature, the safest order is:

1. add admin or security CRUD endpoints for registered vehicles
2. add secure document upload and storage paths
3. add profile search and edit UI
4. add approval, renewal, expiry, and blocking actions
5. consider plate alias history if plate corrections need durable tracking
6. only later consider fuzzy candidate suggestions for OCR near-matches

## Important Rules For Future Agents

- keep registry logic separate from detector, OCR, and camera ingestion code
- keep `vehicle_id` as the internal identity
- do not auto-approve unmatched vehicles
- do not let fuzzy OCR near-matches silently auto-link to a profile
- keep dummy seeding removable once real registration data exists
- prefer schema evolution in `StorageService` over hard resets of the local SQLite database

## Quick Orientation

If you need to continue this feature in a future session, start with:

1. `docs/vehicle-registration-feature.md`
2. `src/services/vehicle_registry_service.py`
3. `src/services/storage_service.py`
4. `src/app.py`
5. `src/api/routes.py`
6. `templates/index.html`
7. `static/js/app.js`
