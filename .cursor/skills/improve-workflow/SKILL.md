---
name: improve-workflow
description: >-
  Improve the EM sprint automation workflow by applying changes consistently
  across skills, rules, commands, agents, and Python scripts. Use when the user
  runs /improve-workflow or asks to update, fix, or extend the EM Cursor workflow.
disable-model-invocation: true
---

# Improve Workflow

**Protocol:** PLAN → VALIDATE → EXECUTE → REPORT

System inventory and pipeline: **`.cursor/WORKFLOW.md`**. Runbook: **`em-orchestrator`** skill.

## Cross-reference matrix

| If you change… | Also update… |
|----------------|--------------|
| Schedule algorithm | `sprint-planning`, `schedule-engine.mdc`, `schedule_engine.py`, tests |
| Issue hierarchy / effort | `jira-domain`, `jira_normalize.py`, `em-config.yaml` |
| Team / summary prefixes | `jira_teams.py`, `jira-domain`, `timeline_breakdown.py`, `bug_effort_breakdown.py`, `jira_normalize.py`, `WORKFLOW.md`, tests |
| Delivery phases / deps | `delivery-flow`, `schedule_engine.py`, `sprint-report` |
| Report format | `sprint-report`, `em-orchestrator`, `render_report.py` |
| New command | command file + `em-workflow.mdc` + `WORKFLOW.md` + orchestrator skill |
| Jira field mapping | `em-config.yaml`, `jira-domain`, `jira_normalize.py`, `sprint_meta.py` |
| Sprint window / epic rollup | `sprint_meta.py`, `render_report.py`, `sprint-report` |
| Timeline / bug sections | respective scripts, `render_report.py`, `sprint-report` |
| MCP fetch protocol | `jira-domain`, `em-orchestrator`, `sprint-analyst` |

## Workflow

1. Read `.cursor/WORKFLOW.md` and files touched by the request
2. Classify: algorithm | domain | report | command | config | test
3. Plan with matrix above → **Improvement Report** → wait for approval unless user gave explicit implement spec
4. Apply edits; run `python3 -m unittest discover scripts/tests`
5. Append **Changelog** below; sync `WORKFLOW.md` if inventory changed

## Improvement Report template

```markdown
## Improvement Report
**Date:** YYYY-MM-DD
**Request:** {summary}
### Files to change
| File | Change |
### Cross-reference checks
- [ ] schedule-engine.mdc ↔ schedule_engine.py
- [ ] WORKFLOW.md ↔ scripts and commands
- [ ] jira-domain ↔ jira_teams.py / config
- [ ] Tests cover new behavior
```

## Hard rules

- Never update one file in isolation when cross-references exist
- Never weaken jira-read-only without explicit user request
- Run unit tests after script changes
- Do not edit `.cursor/plans/`
- One sprint markdown file (no separate `bug-effort-*.md` or `timeline-breakdown-*.md`)

## Changelog

- 2026-06-03 — Token cleanup: `.cursor/WORKFLOW.md` manifest; slimmed sprint-report/jira-domain/improve-workflow; removed `render_bug_report.py` and legacy `timeline-breakdown-*.md`; expanded `.gitignore` for generated reports.
- 2026-06-03 — Workflow inventory sync: `jira_teams.py`, pipe-prefix → Other, member-by-side timeline, Task/Sub-task timeline effort, inline bug effort.
- 2026-06-02 — Jira-driven timeline breakdown (`timeline_breakdown.py`, 6h/day).
- 2026-06-02 — Clickable Jira links (`jira.siteUrl`, `render_report.py`).
- 2026-06-02 — Sprint window from Jira sprint field; epic rollup; `render_report.py`.
- 2026-06-02 — Initial EM workflow.
