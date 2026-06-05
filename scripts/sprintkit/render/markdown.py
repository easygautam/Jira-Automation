"""Markdown cell, link, anchor, and number formatting helpers."""

from __future__ import annotations

from typing import Any


def jira_browse_url(site_url: str, issue_key: str) -> str:
    base = site_url.rstrip("/")
    return f"{base}/browse/{issue_key}"


def resolve_jira_site_url(
    jira_site_url: str | None,
    config: dict[str, Any] | None,
) -> str | None:
    if jira_site_url:
        return jira_site_url
    if config:
        return (config.get("jira") or {}).get("siteUrl")
    return None


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
    limit: int = 4,
) -> str:
    if not keys:
        return "—"
    shown = keys[:limit]
    parts = [jira_issue_link(site_url, k) for k in shown]
    suffix = "…" if len(keys) > limit else ""
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
