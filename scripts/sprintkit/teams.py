"""Step 2 — team detection from Jira summary prefix, Teams field, labels, components."""

from __future__ import annotations

from typing import Any

from sprintkit.config import (
    DEFAULT_TEAM_DELIVERY_PLATFORM,
    DEFAULT_TEAM_FIELD_MAPPING,
    DEFAULT_TEAM_FIELD_UAT_VALUES,
)
from sprintkit.jira_model import get_field

TEAM_OTHER = "other"

# Defaults when teamPrefixMapping is absent from em-config.yaml
_DEFAULT_PREFIX_MAPPING: dict[str, list[str]] = {
    "qa": ["qa"],
    "data_engineering": ["ds", "de"],
    "backend": ["be", "backend", "api", "dag", "ppadmin", "admin"],
    "frontend": ["web", "website", "frontend", "frontent", "fe"],
    "mobile": ["mobile", "app", "android", "ios"],
}

_PREFIX_TEAM_ORDER: tuple[str, ...] = (
    "qa",
    "data_engineering",
    "backend",
    "frontend",
    "mobile",
)


def _casefold(text: str) -> str:
    """Case-insensitive normalize for prefix/alias comparison (BE, be, Be equivalent)."""
    return text.casefold().strip()


def load_prefix_alias_sets(config: dict[str, Any] | None = None) -> dict[str, frozenset[str]]:
    """Build team -> alias set from config teamPrefixMapping (or defaults)."""
    cfg = (config or {}).get("teamPrefixMapping") or {}
    all_teams = set(_DEFAULT_PREFIX_MAPPING) | set(cfg.keys())
    result: dict[str, frozenset[str]] = {}
    for team in all_teams:
        default_aliases = _DEFAULT_PREFIX_MAPPING.get(team, [])
        entry = cfg.get(team) or {}
        aliases = entry.get("aliases") if isinstance(entry, dict) else entry
        if not aliases:
            aliases = default_aliases
        if aliases:
            result[team] = frozenset(_casefold(a) for a in aliases)
    return result


def load_team_field_mapping(config: dict[str, Any] | None = None) -> dict[str, str]:
    return dict((config or {}).get("teamFieldMapping") or DEFAULT_TEAM_FIELD_MAPPING)


def load_team_delivery_platform(config: dict[str, Any] | None = None) -> dict[str, str]:
    merged = dict(DEFAULT_TEAM_DELIVERY_PLATFORM)
    merged.update((config or {}).get("teamDeliveryPlatform") or {})
    for platform in ("backend", "frontend", "mobile"):
        merged.setdefault(platform, platform)
    return merged


def jira_teams_field_value(
    issue: dict[str, Any], config: dict[str, Any] | None = None
) -> str | None:
    """Read Jira Teams select field option label (e.g. Android, Data Engineering)."""
    fields_cfg = (config or {}).get("fields") or {}
    field_id = fields_cfg.get("teams", "customfield_10218")
    raw = get_field(issue, field_id)
    if not raw:
        return None
    if isinstance(raw, dict):
        return raw.get("value") or None
    return str(raw) if raw else None


def team_from_jira_field_value(
    value: str | None, config: dict[str, Any] | None = None
) -> str | None:
    if not value:
        return None
    return load_team_field_mapping(config).get(value)


def team_from_jira_field(
    issue: dict[str, Any], config: dict[str, Any] | None = None
) -> str | None:
    return team_from_jira_field_value(jira_teams_field_value(issue, config), config)


def is_jira_teams_uat_value(value: str | None, config: dict[str, Any] | None = None) -> bool:
    if not value:
        return False
    uat_values = (config or {}).get("teamFieldUatValues") or DEFAULT_TEAM_FIELD_UAT_VALUES
    return value in uat_values


def delivery_platform(team: str | None, config: dict[str, Any] | None = None) -> str | None:
    """Map internal team key to delivery platform (backend | frontend | mobile)."""
    if not team or team == TEAM_OTHER:
        return None
    return load_team_delivery_platform(config).get(team)


def first_summary_prefix(summary: str) -> str | None:
    """First segment before '|' (strip). None if summary has no pipe."""
    if "|" not in summary:
        return None
    return summary.split("|", 1)[0].strip()


def _prefix_tokens(prefix: str) -> list[str]:
    """Case-insensitive tokens from the first pipe segment (whole segment + first word)."""
    p = _casefold(prefix).rstrip(":")
    if not p:
        return []
    tokens = [p]
    first_word = p.split()[0]
    if first_word and first_word not in tokens:
        tokens.append(first_word)
    return tokens


def _token_matches_alias(token: str, alias: str) -> bool:
    """True when token and alias match ignoring case (exact or alias + remainder)."""
    t = _casefold(token).rstrip(":")
    a = _casefold(alias).rstrip(":")
    if not t or not a:
        return False
    if t == a:
        return True
    # e.g. "be enhancement" matches alias "be"
    return t.startswith(f"{a} ") or t.startswith(f"{a}-")


def team_from_prefix_tokens(
    tokens: list[str],
    alias_sets: dict[str, frozenset[str]],
) -> str | None:
    order = _PREFIX_TEAM_ORDER
    for team in order:
        aliases = alias_sets.get(team, frozenset())
        for t in tokens:
            for alias in aliases:
                if _token_matches_alias(t, alias):
                    return team
    return None


def team_from_first_prefix(
    summary: str,
    alias_sets: dict[str, frozenset[str]] | None = None,
) -> str | None:
    """Map first pipe prefix to team key using configured aliases."""
    prefix = first_summary_prefix(summary)
    if not prefix:
        return None
    sets = alias_sets or load_prefix_alias_sets()
    return team_from_prefix_tokens(_prefix_tokens(prefix), sets)


def team_from_summary_start(
    summary: str,
    alias_sets: dict[str, frozenset[str]] | None = None,
) -> str | None:
    """Map team when summary has no pipe but starts with a known alias."""
    sets = alias_sets or load_prefix_alias_sets()
    folded = _casefold(summary)
    all_aliases: list[tuple[str, str]] = []
    for team, aliases in sets.items():
        for alias in aliases:
            all_aliases.append((alias, team))
    for alias, team in sorted(all_aliases, key=lambda x: len(x[0]), reverse=True):
        if folded.startswith(alias + " ") or folded.startswith(alias + "|"):
            return team
    return None


def team_from_title(summary: str, config: dict[str, Any] | None = None) -> str | None:
    """Team from summary title only (pipe prefix or start-with alias)."""
    alias_sets = load_prefix_alias_sets(config)
    if "|" in summary:
        return team_from_first_prefix(summary, alias_sets)
    return team_from_summary_start(summary, alias_sets)


def team_from_issue(
    issue: dict[str, Any],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None = None,
) -> str:
    summary = (get_field(issue, "summary") or "").strip()
    alias_sets = load_prefix_alias_sets(config)

    from_title = team_from_title(summary, config)
    if from_title:
        return from_title

    from_field = team_from_jira_field(issue, config)
    if from_field:
        return from_field

    labels = [x.lower() for x in (get_field(issue, "labels") or [])]
    components = [(c.get("name") or "").lower() for c in (get_field(issue, "components") or [])]
    haystack = " ".join(labels + components)
    for team, keywords in (teams_cfg or {}).items():
        for kw in keywords:
            if kw.lower() in haystack:
                return team

    lower = summary.lower()
    for team, keywords in (teams_cfg or {}).items():
        for kw in keywords:
            if kw.lower() in lower:
                return team
    return TEAM_OTHER
