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
| Report format | `sprint-report`, `em-orchestrator`, `render_report.py`, `schedule_delta.py` |
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

- 2026-06-05 — Report: all Jira issue keys render as browse links via `jira.siteUrl` (`resolve_jira_site_url`, timeline Issues column, bug Epic ID); sprint-report skill updated.
- 2026-06-05 — Sprint window rule (all statuses, sprint start→end); Teams plan team summary uses a single combined `Leave (h)` (planned+unplanned) while the member breakdown keeps detailed Planned leave + Unplanned delay; execution-stage `Delay (h)` column removed (folded into combined `Leave (h)`); execution stages omit platforms with no Jira tasks (`hasWork`); all timeline `Start`/`End` render as `—` and epic/platform delivery-window + go-live + calendar-day lines removed — **calendar dates deferred** (sprint-window date rule to be implemented later).
- 2026-06-03 — Execution stages: per-platform pipelines (Backend/Web/Mobile), QA cross-platform Test planning, prefix `| Assessment` mapping, `QA | Web/Mobile/BE` streams, synthetic Bug fixes / Stage final testing buffers, separate Pre-Prod/UAT/Ready for release and Prod release/Prod final testing; report section renamed from Task breakdown.
- 2026-06-03 — Epic sort: Jira Rank (LexoRank / `fields.rank`) for Delivery items, Timeline, and Bug fix effort; shared `epic_jira_sort_key` in `jira_normalize.py`.
- 2026-06-03 — Delivery items sort: PRD-titled epics first, then nearest due date (`delivery_epic_sort_key`). *(superseded by Jira Rank sort)*
- 2026-06-03 — Bug DQ: `bugNoWorklogStatuses` (Not a Bug) skip missing-logged-time flags and unscheduled noise.
- 2026-06-03 — Code cleanup: shared epic helpers in `jira_normalize.py`, removed dead code, deduped DQ index, simplified rollup.
- 2026-06-03 — Schedule Delta (`schedule_delta.py`); config-driven `statusPhaseMap`; unscheduled breakdown narrative; WORKFLOW inventory + DQ CLI note.
- 2026-06-03 — Status-aware bug DQ: active bugs skip time flags; past-active bugs need worklog (`Missing logged time`); DQ reason summary + consolidated ticket rows; split recommended actions.
- 2026-06-03 — Bug fix effort: one row per sprint epic (including zero bugs); Bugs column; order matches Delivery items.
- 2026-06-03 — Bug fix effort: epic table (Epic ID, Name, Backend/Web/Mobile); member detail without team column. Schedule index removed; **Team tasks plan** replaces Schedule by assignee.
- 2026-06-03 — Bug fix effort: hours from `timespent` (worklog) only; Original Estimate excluded from rollup.
- 2026-06-03 — Delivery items: epic Title links to Timeline PRD detail (`#prd-{epicKey}`).
- 2026-06-03 — Schedule by assignee: team index table (start/end/total effort) with anchor links to per-member task tables.
- 2026-06-03 — Bug effort from time spent: `effective_estimate_seconds` uses `timespent` when OE empty; DQ skips missing-estimate for logged bugs; fetch includes `timespent`.
- 2026-06-03 — No dependency violations when blocker unscheduled; Schedule by assignee drops Start/Due columns (dates are engine-calculated, not Jira).
- 2026-06-03 — Data quality flags: per-member tables (Ticket, Title, Reason) via `data_quality.py`.
- 2026-06-03 — Bug fix effort: epic-wise member/team hour totals only (removed per-bug issue lists from JSON and report).
- 2026-06-03 — Schedule by assignee: Story column replaced with Task title (Jira summary on the task).
- 2026-06-03 — Removed Mobile/Web integration buffer (10% extra duration and report notes); BE start-after dependency unchanged.
- 2026-06-03 — Token cleanup: `.cursor/WORKFLOW.md` manifest; slimmed sprint-report/jira-domain/improve-workflow; removed `render_bug_report.py` and legacy `timeline-breakdown-*.md`; expanded `.gitignore` for generated reports.
- 2026-06-03 — Workflow inventory sync: `jira_teams.py`, pipe-prefix → Other, member-by-side timeline, Task/Sub-task timeline effort, inline bug effort.
- 2026-06-02 — Jira-driven timeline breakdown (`timeline_breakdown.py`, 6h/day).
- 2026-06-02 — Clickable Jira links (`jira.siteUrl`, `render_report.py`).
- 2026-06-02 — Sprint window from Jira sprint field; epic rollup; `render_report.py`.
- 2026-06-02 — Initial EM workflow.
