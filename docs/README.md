# Project Docs

This folder holds the human-facing documentation for the USM license plate recognition prototype.

Start here:

- [architecture.md](architecture.md): finalized target architecture, runtime layers, module boundaries, and data flow
- [CONTEXT.md](CONTEXT.md): consolidated project context, current scope, and planned entry/exit roadmap
- [setup.md](setup.md): local setup, dependencies, and model placement
- [CODEX_HANDOFF.md](CODEX_HANDOFF.md): project-specific implementation guardrails and future-session notes for continuing development
- [data-workflow.md](data-workflow.md): image preparation, YOLO splits, OCR crop generation, and aggregated OCR evaluation assets
- [ocr-labeling-workflow.md](ocr-labeling-workflow.md): manual ground-truth transcription process for OCR crops and the current completed labeling state
- [evaluation.md](evaluation.md): OCR and end-to-end evaluation workflow, including direct OCR evaluation from prepared crop truth files
- [implementation-roadmap.md](implementation-roadmap.md): consolidated next steps, implementation phases, milestones, and definition of done
- [backend-implementation-prompt.md](backend-implementation-prompt.md): standalone backend/system implementation prompt for camera roles, events, sessions, SQLite, and API work
- [frontend-implementation-prompt.md](frontend-implementation-prompt.md): standalone frontend/dashboard implementation prompt for the operator UI
- [full-system-implementation-prompt.md](full-system-implementation-prompt.md): copy-pasteable implementation prompt for building the next local-system stage from the documented architecture
- [phase-1-plan.md](phase-1-plan.md): detailed execution plan for detector fine-tuning, OCR evaluation, end-to-end evaluation, outputs, and success criteria
- [session-flow.md](session-flow.md): planned entry and exit session lifecycle for campus vehicle tracking
- [missing-pieces.md](missing-pieces.md): major missing features and implementation gaps between the current prototype and the target system
- [known-issues.md](known-issues.md): current limitations and practical caveats

Suggested reading order for a new contributor:

1. Read `README.md` in the repo root.
2. Read [setup.md](setup.md).
3. Read [architecture.md](architecture.md).
4. Read [implementation-roadmap.md](implementation-roadmap.md) when planning what to build next.
5. Read [session-flow.md](session-flow.md) before implementing entry or exit tracking.
6. Read [missing-pieces.md](missing-pieces.md) for a shorter gap summary.
7. Use the data and evaluation docs only when working on those parts of the project.
