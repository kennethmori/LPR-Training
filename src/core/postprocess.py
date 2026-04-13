from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class PlateTextPostProcessor:
    def __init__(self, settings: dict[str, Any], rules_path: Path | None = None) -> None:
        self.settings = settings
        self.rules = self._load_rules(rules_path) if rules_path else {}

    def _load_rules(self, rules_path: Path) -> dict[str, Any]:
        if not rules_path.exists():
            return {}
        with rules_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def clean(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text
        if self.settings.get("uppercase", True):
            cleaned = cleaned.upper()
        if self.settings.get("collapse_spaces", True):
            cleaned = re.sub(r"\s+", "", cleaned)
        if self.settings.get("strip_non_alnum", True):
            cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)

        if self.settings.get("apply_soft_rules") and self.rules.get("enabled"):
            substitutions = self.rules.get("substitutions", {})
            for source, target in substitutions.items():
                cleaned = cleaned.replace(source, target)

            pattern = self.rules.get("allowed_pattern")
            if pattern and not re.fullmatch(pattern, cleaned):
                return ""

        return cleaned
