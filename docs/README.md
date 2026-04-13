# Project Docs

This folder holds the human-facing documentation for the USM license plate recognition prototype.

Start here:

- [architecture.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/architecture.md): system structure, request flow, and component responsibilities
- [CONTEXT.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/CONTEXT.md): consolidated project context, current scope, and planned entry/exit roadmap
- [setup.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/setup.md): local setup, dependencies, and model placement
- [data-workflow.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/data-workflow.md): image preparation, YOLO splits, OCR crop generation, and aggregated OCR evaluation assets
- [ocr-labeling-workflow.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/ocr-labeling-workflow.md): manual ground-truth transcription process for OCR crops and the current completed labeling state
- [evaluation.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/evaluation.md): OCR and end-to-end evaluation workflow, including direct OCR evaluation from prepared crop truth files
- [implementation-roadmap.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/implementation-roadmap.md): consolidated next steps, implementation phases, milestones, and definition of done
- [phase-1-plan.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/phase-1-plan.md): detailed execution plan for detector fine-tuning, OCR evaluation, end-to-end evaluation, outputs, and success criteria
- [session-flow.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/session-flow.md): planned entry and exit session lifecycle for campus vehicle tracking
- [missing-pieces.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/missing-pieces.md): major missing features and implementation gaps between the current prototype and the target system
- [known-issues.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/known-issues.md): current limitations and practical caveats

Suggested reading order for a new contributor:

1. Read `README.md` in the repo root.
2. Read [setup.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/setup.md).
3. Read [architecture.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/architecture.md).
4. Read [implementation-roadmap.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/implementation-roadmap.md) when planning what to build next.
5. Read [session-flow.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/session-flow.md) before implementing entry or exit tracking.
6. Read [missing-pieces.md](C:/4%20BSCS/4%20bscs%202nd%20sem/IntelligentSystems/plate/docs/missing-pieces.md) for a shorter gap summary.
7. Use the data and evaluation docs only when working on those parts of the project.
