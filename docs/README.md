# Project Docs

This folder holds the human-facing documentation for the USM license plate recognition prototype.

Start here:

- [architecture.md](architecture.md): target architecture plus the current runtime layers, module boundaries, and data flow
- [CONTEXT.md](CONTEXT.md): current implementation snapshot, current scope, and remaining gaps
- [setup.md](setup.md): local setup, detector backend options, runtime outputs, and model placement
- [CODEX_HANDOFF.md](CODEX_HANDOFF.md): future-session handoff notes and project guardrails based on the current codebase
- [data-workflow.md](data-workflow.md): image preparation, YOLO splits, OCR crop generation, and aggregated OCR evaluation assets
- [ocr-labeling-workflow.md](ocr-labeling-workflow.md): manual ground-truth transcription process for OCR crops and the current completed labeling state
- [evaluation.md](evaluation.md): OCR and end-to-end evaluation workflow, including direct OCR evaluation from prepared crop truth files
- [implementation-roadmap.md](implementation-roadmap.md): next priorities from the current session-tracking baseline
- [session-flow.md](session-flow.md): implemented entry and exit session lifecycle and matching rules
- [missing-pieces.md](missing-pieces.md): major remaining gaps after the current session-tracking implementation
- [known-issues.md](known-issues.md): current limitations and practical caveats
- [backend-implementation-prompt.md](backend-implementation-prompt.md): reference prompt for rebuilding or extending the backend/session layer
- [frontend-implementation-prompt.md](frontend-implementation-prompt.md): reference prompt for rebuilding or extending the operator dashboard
- [frontend-maintainability.md](frontend-maintainability.md): vanilla JS dashboard maintainability rules, rendering patterns, and extension workflow
- [full-system-implementation-prompt.md](full-system-implementation-prompt.md): reference prompt for large rebuilds or cross-cutting extensions
- [phase-1-plan.md](phase-1-plan.md): detector, OCR, and end-to-end evaluation plan for the recognition-quality side of the project

Suggested reading order for a new contributor:

1. Read `README.md` in the repo root.
2. Read [setup.md](setup.md).
3. Read [architecture.md](architecture.md).
4. Read [CONTEXT.md](CONTEXT.md).
5. Read [missing-pieces.md](missing-pieces.md).
6. Read [known-issues.md](known-issues.md).
7. Read [session-flow.md](session-flow.md) before changing session rules.
8. Read [implementation-roadmap.md](implementation-roadmap.md) when planning what to improve next.

The prompt docs are useful for larger rebuilds, but they are not the source of truth for current repo status.
