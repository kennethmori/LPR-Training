from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

ARTIFACTS_ROOT = Path(__file__).resolve().parents[2] / "outputs"


def resolve_artifact_path(raw_path: str) -> Path:
    raw_candidate = str(raw_path or "").strip()
    if not raw_candidate:
        raise HTTPException(status_code=400, detail="Missing artifact path.")
    candidate = Path(raw_candidate)
    resolved = candidate.expanduser().resolve()
    try:
        resolved.relative_to(ARTIFACTS_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Artifact path is outside outputs.") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")
    return resolved
