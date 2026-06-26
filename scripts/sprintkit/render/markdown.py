"""Markdown cell, link, anchor, and number formatting helpers."""

from __future__ import annotations

import json
import re
from typing import Any

_ATLASSIAN_SITE_RE = re.compile(r"https://[a-zA-Z0-9-]+\.atlassian\.net")
# Bare keys only — skip keys already in [KEY](url) or .../browse/KEY
_BARE_ISSUE_KEY_RE = re.compile(
    r"(?<!\[)(?<!browse/)(?<!/)\b([A-Z][A-Z0-9]+-\d+)\b(?!\]\()"
)


def jira_browse_url(site_url: str, issue_key: str) -> str:
    base = site_url.rstrip("/")
    return f"{base}/browse/{issue_key}"


def derive_jira_site_url_from_issues(issues: list[dict[str, Any]] | None) -> str | None:
    """Infer site base URL from Jira issue payloads (iconUrl, self, etc.)."""
    if not issues:
        return None
    for issue in issues:
        try:
            blob = json.dumps(issue, default=str)
        except (TypeError, ValueError):
            continue
        match = _ATLASSIAN_SITE_RE.search(blob)
        if match:
            return match.group(0)
    return None


def resolve_jira_site_url(
    jira_site_url: str | None,
    config: dict[str, Any] | None,
    issues: list[dict[str, Any]] | None = None,
) -> str | None:
    """Resolve browse base URL: CLI override → config → derive from issues."""
    if jira_site_url:
        return jira_site_url.rstrip("/")
    if config:
        configured = (config.get("jira") or {}).get("siteUrl")
        if configured:
            return str(configured).rstrip("/")
    return derive_jira_site_url_from_issues(issues)


def linkify_bare_issue_keys(
    text: str,
    site_url: str | None,
    *,
    project_key: str | None = None,
) -> str:
    """Wrap any remaining bare PROJ-123 keys as browse links (idempotent)."""
    if not site_url or not text:
        return text

    def _repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if project_key and not key.startswith(f"{project_key}-"):
            return key
        return jira_issue_link(site_url, key)

    return _BARE_ISSUE_KEY_RE.sub(_repl, text)


def jira_issue_link(site_url: str | None, issue_key: str | None) -> str:
    if not issue_key:
        return "—"
    if site_url:
        return f"[{issue_key}]({jira_browse_url(site_url, issue_key)})"
    return issue_key


def jira_issue_keys_linked(
    site_url: str | None,
    keys: list[str] | None,
    *,
    limit: int | None = None,
) -> str:
    """Comma-separated browse links for issue keys. No limit by default (all keys)."""
    if not keys:
        return "—"
    shown = keys if limit is None else keys[:limit]
    parts = [jira_issue_link(site_url, k) for k in shown]
    suffix = "…" if limit is not None and len(keys) > limit else ""
    return ", ".join(parts) + suffix


def escape_md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def format_effort(seconds: int | None) -> str:
    if not seconds:
        return "—"
    hours = seconds / 3600
    if hours >= 8:
        days = hours / 8
        return f"{days:.1f}d" if days != int(days) else f"{int(days)}d"
    return f"{int(hours)}h" if hours == int(hours) else f"{hours:.1f}h"


def fmt_hours(val: float | None) -> str:
    if val is None or val == 0:
        return "—"
    return str(val) if val == int(val) else f"{val:.1f}"


def fmt_hours_with_unit(val: float | None) -> str:
    """Compact hours for inline detail strings (e.g. 1h, 1.5h)."""
    if val is None or val == 0:
        return "0h"
    if val == int(val):
        return f"{int(val)}h"
    return f"{val:.1f}".rstrip("0").rstrip(".") + "h"


def fmt_date(val: str | None) -> str:
    return val or "TBD"


def fmt_resources(val: float | None) -> str:
    if val is None or val <= 0:
        return "—"
    return f"{val:.1f}"


def epic_prd_anchor(epic_key: str) -> str:
    """Stable fragment id for Timeline breakdown PRD section (epic key)."""
    return f"prd-{epic_key.lower()}"


def epic_title_link(summary: str, epic_key: str, link_to_timeline: bool) -> str:
    """Title cell: anchor to PRD timeline detail when breakdown exists for epic."""
    text = escape_md_cell(summary)
    if link_to_timeline:
        return f"[{text}](#{epic_prd_anchor(epic_key)})"
    return text
