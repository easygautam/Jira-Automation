#!/usr/bin/env python3
"""Team detection from Jira issue fields (shared by normalize, timeline, bug reports)."""

from __future__ import annotations

from typing import Any

# Canonical task names that must not match via keywords when first prefix is QA
_DEV_TASK_NAMES = frozenset(
    {
        "BE development",
        "Web development",
        "Mobile development",
        "BE Assessment",
        "Web Assessment",
        "Mobile Assessment",
    }
)

TEAM_OTHER = "other"

# Defaults when teamPrefixMapping is absent from em-config.yaml
_DEFAULT_PREFIX_MAPPING: dict[str, list[str]] = {
    "qa": ["qa"],
    "backend": ["be", "backend", "api", "dag", "ppadmin", "admin"],
    "frontend": ["web", "website", "frontend", "frontent", "fe"],
    "mobile": ["mobile", "app", "android", "ios"],
}


def get_field(issue: dict[str, Any], name: str) -> Any:
    return (issue.get("fields") or {}).get(name)


def load_prefix_alias_sets(config: dict[str, Any] | None = None) -> dict[str, frozenset[str]]:
    """Build team -> alias set from config teamPrefixMapping (or defaults)."""
    cfg = (config or {}).get("teamPrefixMapping") or {}
    result: dict[str, frozenset[str]] = {}
    for team, default_aliases in _DEFAULT_PREFIX_MAPPING.items():
        entry = cfg.get(team) or {}
        aliases = entry.get("aliases") if isinstance(entry, dict) else entry
        if not aliases:
            aliases = default_aliases
        result[team] = frozenset(_casefold(a) for a in aliases)
    return result


def _casefold(text: str) -> str:
    """Case-insensitive normalize for prefix/alias comparison (BE, be, Be equivalent)."""
    return text.casefold().strip()


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
    order = ("qa", "backend", "frontend", "mobile")
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


def qa_work_stream(summary: str) -> str:
    """When first prefix is QA, infer web vs mobile stream from later pipe segments."""
    parts = [p.strip().lower() for p in summary.split("|")]
    if len(parts) < 2:
        return "web"
    context = " ".join(parts[1:])
    if any(x in context for x in ("app", "mobile", "android", "ios")):
        return "mobile"
    if any(x in context for x in ("web", "website", "mweb", "frontend", "fe", "admin")):
        return "web"
    return "web"


def team_from_issue(
    issue: dict[str, Any],
    teams_cfg: dict[str, list[str]],
    config: dict[str, Any] | None = None,
) -> str:
    summary = (get_field(issue, "summary") or "").strip()
    alias_sets = load_prefix_alias_sets(config)

    if "|" in summary:
        from_prefix = team_from_first_prefix(summary, alias_sets)
        return from_prefix if from_prefix else TEAM_OTHER

    from_start = team_from_summary_start(summary, alias_sets)
    if from_start:
        return from_start

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


def task_from_pipe_prefix_team(
    summary: str,
    team: str,
    timeline_cfg: dict[str, Any],
    issuetype: str,
    config: dict[str, Any] | None = None,
) -> str | None:
    """
    When summary uses a recognized first pipe prefix, map Task/Sub-task to default
    canonical row for that team (e.g. BE | Enhancement -> BE development).
    """
    if "|" not in summary:
        return None
    alias_sets = load_prefix_alias_sets(config)
    if team_from_first_prefix(summary, alias_sets) is None:
        return None
    if team in (TEAM_OTHER, "qa"):
        return None
    itype = (issuetype or "").lower()
    if itype not in ("task", "sub-task", "subtask"):
        return None
    if "assessment" in summary.lower():
        return None
    defaults = timeline_cfg.get("defaultTaskByTeam") or {}
    return defaults.get(team)


def mapping_rule_applies(rule: dict[str, Any], summary: str, team: str) -> bool:
    """Keyword match; skip dev-task rules when title is QA-prefixed."""
    task = rule.get("task")
    if task in _DEV_TASK_NAMES and team == "qa":
        return False
    keywords = [k.lower() for k in rule.get("keywords") or []]
    lower = summary.lower()
    return bool(keywords) and any(kw in lower for kw in keywords)
