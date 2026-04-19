# Known Issues

## Current Scope Limits

- The live pipeline currently uses only the highest-confidence detection as the final candidate.
- The app is centered on one detector class: `plate_number`.
- OCR uses pretrained engines first and does not yet include a custom-trained recognizer.
- No formal automated test suite is configured yet.

## Runtime Caveats

- If `models/detector/best.pt` is missing while the detector backend is set to `ultralytics`, the detector stays unavailable and no detections are produced.
- If OCR libraries are missing, OCR remains unavailable and recognition results will be empty.
- The app still starts in these cases, which is intentional so readiness can be inspected through the UI and status endpoint.
- Large upload payloads are now constrained by `configs/app_settings.yaml` under `uploads`, so unsupported formats or oversized files are rejected.

## API and Codebase Notes

- `src/api/schemas.py` defines response models, but many routes still return dict payloads instead of strict schema instances.
- The pipeline prepares output directories, but current user-visible image output is mainly returned through base64 payload fields for the frontend.
- Camera processing only runs inference on every Nth frame to reduce load.
- Event history now includes ignored decisions (`ignored_low_quality`, `ignored_ambiguous_near_match`, `ignored_duplicate`) for better observability.

## Near-Term Engineering Priorities

- Add automated tests for session rules, storage behavior, and API boundaries.
- Tighten API response typing so returned payloads fully align with declared response models.
- Add database migration/versioning support if schema evolution becomes frequent.

## Documentation Notes

- `README.md` is the short project overview.
- `AGENTS.md` is for repo-specific coding guidance.
- `docs/` is the main place for detailed human-facing project documentation.
