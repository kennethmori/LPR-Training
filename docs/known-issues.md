# Known Issues

## Current Scope Limits

- The live pipeline currently uses only the highest-confidence detection as the final candidate.
- The app is centered on one detector class: `plate_number`.
- OCR uses pretrained engines first and does not yet include a custom-trained recognizer.
- No formal automated test suite is configured yet.
- Entry and exit session tracking is not implemented yet.

## Runtime Caveats

- If `models/detector/best.pt` is missing, the detector stays unavailable and no detections are produced.
- If OCR libraries are missing, OCR remains unavailable and recognition results will be empty.
- The app still starts in these cases, which is intentional so readiness can be inspected through the UI and status endpoint.

## API and Codebase Notes

- `src/api/schemas.py` defines response models, but routes currently return plain dict payloads.
- The pipeline prepares output directories, but current user-visible image output is mainly returned through base64 payload fields for the frontend.
- Camera processing only runs inference on every Nth frame to reduce load.
- The current live stack assumes a single camera source and does not yet model `entry` and `exit` roles.

## Planned Next Step

- Add dual-camera support or role-aware camera management.
- Add a session service that opens sessions on entry and closes them on exit.
- Add durable storage for active and completed vehicle sessions.
- Keep recognition and session lifecycle logic separate.

## Documentation Notes

- `README.md` is the short project overview.
- `AGENTS.md` is for repo-specific coding guidance.
- `docs/` is the main place for detailed human-facing project documentation.
