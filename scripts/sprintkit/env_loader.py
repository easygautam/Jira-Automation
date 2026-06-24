"""Load local env files for local + Cursor Cloud agent runs.

Priority (highest wins — never overwrite an existing os.environ value):
  1. Process environment (Cursor Cloud Secrets inject here as Runtime Secrets)
  2. Files listed in em-config.yaml `slack.envFiles` (default: .env.local, .env)
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_DEFAULT_ENV_FILES = (".env.local", ".env")
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from start (or cwd) to find repo root via .git or em-config."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        if (directory / ".git").exists():
            return directory
        if (directory / ".cursor" / "config" / "em-config.yaml").exists():
            return directory
    return current


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_env_file(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines; ignores comments and blank lines."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_LINE.match(line)
        if not match:
            continue
        key, raw_value = match.group(1), match.group(2)
        if "#" in raw_value and not (raw_value.startswith('"') or raw_value.startswith("'")):
            raw_value = raw_value.split("#", 1)[0].rstrip()
        result[key] = _strip_quotes(raw_value.strip())
    return result


def load_env_files(
    config: dict[str, Any] | None = None,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    """Load env files into os.environ without overriding existing keys."""
    root = repo_root or find_repo_root()
    slack_cfg = (config or {}).get("slack") or {}
    filenames = slack_cfg.get("envFiles") or list(_DEFAULT_ENV_FILES)

    loaded: list[str] = []
    for name in filenames:
        path = root / name
        if not path.is_file():
            continue
        for key, value in parse_env_file(path.read_text(encoding="utf-8")).items():
            if key not in os.environ:
                os.environ[key] = value
        loaded.append(str(path))
    return loaded


def slack_token_setup_hint(config: dict[str, Any] | None = None) -> str:
    slack_cfg = (config or {}).get("slack") or {}
    env_name = slack_cfg.get("botTokenEnv") or "SLACK_BOT_TOKEN"
    return (
        f"Set {env_name} via one of:\n"
        f"  • Local: copy .env.example → .env.local and add {env_name}=xoxb-…\n"
        f"  • Cursor Cloud: Dashboard → Cloud Agents → Secrets → add {env_name} "
        f"(Runtime Secret recommended)\n"
        f"  • Shell: export {env_name}=xoxb-…"
    )
