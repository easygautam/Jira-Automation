"""Shared CLI helpers for sprintkit entry scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sprintkit.env_loader import find_repo_root


def load_issues(path: str | Path) -> list[dict]:
    """Load issues from a JSON list or `{issues: [...]}` wrapper."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("issues", payload)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def resolve_config_path(config_arg: str, *, repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    path = Path(config_arg)
    if not path.is_absolute():
        path = root / path
    return path


def resolve_canvas_dir(config: dict[str, Any], repo_root: Path | None = None) -> Path:
    """Resolve Cursor canvases directory (config override or managed project path)."""
    root = repo_root or find_repo_root()
    workflow = (config.get("workflow") or {})
    configured = workflow.get("canvasDir")
    if configured:
        return Path(configured).expanduser()

    slug = str(root.resolve()).replace("/", "-").lstrip("-")
    if not slug.startswith("Users-"):
        slug = f"Users-{slug}"
    return Path.home() / ".cursor/projects" / slug / "canvases"


def default_canvas_path(
    epic_key: str,
    config: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> Path:
    return resolve_canvas_dir(config, repo_root) / f"epic-{epic_key.upper()}.canvas.tsx"


def require_issues_file(path: str | Path) -> Path:
    issues_path = Path(path)
    if not issues_path.is_file():
        print(f"Issues file not found: {issues_path}", file=sys.stderr)
        sys.exit(1)
    return issues_path
