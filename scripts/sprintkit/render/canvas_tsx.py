"""Generate Cursor Canvas .tsx files from epic estimation canvas JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TEMPLATE_NAME = "epic-estimation.canvas.tsx"
_EPIC_DATA_MARKER = "__EPIC_DATA_PLACEHOLDER__"


def _template_path() -> Path:
    return Path(__file__).resolve().parents[2] / "templates" / _TEMPLATE_NAME


def render_epic_canvas_tsx(canvas_data: dict[str, Any]) -> str:
    """Embed pipeline canvas JSON into the epic estimation canvas template."""
    template = _template_path().read_text(encoding="utf-8")
    if _EPIC_DATA_MARKER in template:
        payload = json.dumps(canvas_data, indent=2, ensure_ascii=False)
        return template.replace(_EPIC_DATA_MARKER, payload)

    # Fallback: replace the default EPIC_DATA object block.
    pattern = re.compile(
        r"/\*\* Replace EPIC_DATA.*?\*/\s*const EPIC_DATA = \{.*?\n\};",
        re.DOTALL,
    )
    payload = json.dumps(canvas_data, indent=2, ensure_ascii=False)
    replacement = f"const EPIC_DATA = {payload};"
    updated, count = pattern.subn(replacement, template, count=1)
    if count != 1:
        raise ValueError("Could not locate EPIC_DATA block in canvas template")
    return updated


def write_epic_canvas(canvas_data: dict[str, Any], path: Path) -> Path:
    """Write a .canvas.tsx file and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_epic_canvas_tsx(canvas_data), encoding="utf-8")
    return path
