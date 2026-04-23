# Known Issues

## Current Scope Limits

- The live pipeline currently uses only the highest-confidence detection as the final candidate.
- The app is centered on one detector class: `plate_number`.
- OCR uses pretrained engines first and does not yet include a custom-trained recognizer.
- Automated tests now cover core detector, pipeline, session, tracking, registry, and key API settings/session workflows, but long-running camera and full dual-camera integration coverage is still limited.

## Runtime Caveats

- If `models/detector/yolo26nbest.pt` is missing while the detector backend is set to `ultralytics`, the detector stays unavailable and no detections are produced.
- If OCR libraries are missing, OCR remains unavailable and recognition results will be empty.
- The app still starts in these cases, which is intentional so readiness can be inspected through the UI and status endpoint.
- Large upload payloads are now constrained by `configs/app_settings.yaml` under `uploads`, so unsupported formats or oversized files are rejected.

## API and Codebase Notes

- `src/api/schemas.py` defines response models for most data endpoints, but some utility, auth, and streaming routes still return ad hoc responses.
- The pipeline prepares output directories, but current user-visible image output is mainly returned through base64 payload fields for the frontend.
- Camera processing only runs inference on every Nth frame to reduce load.
- Event history now includes ignored decisions (`ignored_low_quality`, `ignored_ambiguous_near_match`, `ignored_duplicate`) for better observability.

## Near-Term Engineering Priorities

- Expand automated coverage for long-running camera loops, video upload paths, and end-to-end dual-role session flows.
- Tighten API response typing so returned payloads fully align with declared response models.
- Add database migration/versioning support if schema evolution becomes frequent.

## Documentation Notes

- `README.md` is the short project overview.
- `AGENTS.md` is for repo-specific coding guidance.
- `docs/` is the main place for detailed human-facing project documentation.
