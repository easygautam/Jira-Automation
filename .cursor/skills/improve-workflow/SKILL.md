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

System inventory and pipeline: **`.cursor/WORKFLOW.md`**. Runbook: **`sprint-report`** skill.

## Cross-reference matrix

| If you change… | Also update… |
|----------------|--------------|
| Schedule algorithm | `sprint-report` skill, `schedule-engine.mdc`, `sprintkit/schedule.py`, tests |
| Issue hierarchy / effort | `jira-domain`, `sprintkit/normalize.py`, `sprintkit/jira_model.py`, `em-config.yaml` |
| Team / summary prefixes | `sprintkit/teams.py`, `sprintkit/stages.py`, `jira-domain`, `delivery-flow`, `WORKFLOW.md`, tests |
| Delivery phases / deps | `delivery-flow`, `sprintkit/schedule.py`, `sprintkit/stages.py`, `sprint-report` |
| Report format | `sprint-report`, `sprintkit/render/*`, tests |
| New option / command | matching command + skill + `em-workflow.mdc` + `WORKFLOW.md` + entry script |
| Epic estimation / stage dates | `epic-estimation` skill, `stage_dates.py`, `epic_pipeline.py`, `delivery-flow`, tests |
| Jira field mapping | `em-config.yaml`, `jira-domain`, `sprintkit/normalize.py`, `sprintkit/sprint_window.py` |
| Sprint window / epic rollup | `sprintkit/sprint_window.py`, `sprintkit/render/sections.py`, `sprint-report` |
| Timeline / bug sections | `sprintkit/timeline.py`, `sprintkit/bugs.py`, `sprintkit/render/sections.py`, `sprint-report` |
| MCP fetch protocol | `jira-domain`, `sprint-report` skill, `sprint-analyst` agent |

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
- [ ] schedule-engine.mdc ↔ sprintkit/schedule.py
- [ ] WORKFLOW.md ↔ scripts and commands
- [ ] jira-domain ↔ sprintkit/teams.py + stages.py / config
- [ ] Tests cover new behavior
```

## Hard rules

- Never update one file in isolation when cross-references exist
- Never weaken jira-read-only without explicit user request
- Run unit tests after script changes
- Do not edit `.cursor/plans/`
- One sprint markdown file (no separate `bug-effort-*.md` or `timeline-breakdown-*.md`)

## Changelog

- 2026-06-24 — **DS/DE title prefixes:** `DS |` and `DE |` map to Data Engineering (`teamPrefixMapping`); Tech Solutioning / Development on Backend delivery platform; tests + docs updated.
- 2026-06-24 — **Teams field fallback:** Jira Teams select (`fields.teams` / `customfield_10218`) as secondary team source when title pipe-prefix fails; `teamFieldMapping`, `teamDeliveryPlatform`, `teamFieldUatValues` in config; Data Engineering & DevOps separate Teams-plan rows on Backend delivery Development stage; Product/Analytics → UAT; `delivery_platform()` for schedule deps; docs/tests/WORKFLOW updated.
- 2026-06-24 — **Multi-project support:** `resolve_project_key()` + `project_key_from_issue_key()` in `config.py`; sprint-report resolves project via user/CLI/config; epic commands derive project from epic key and drop `--project`; epic JQL no longer filters by project; removed VP hardcoded CLI defaults; docs/skills/WORKFLOW updated.
- 2026-06-23 — **`/epic-estimation` command:** epic-scoped fetch (no sprint filter), `stage_dates.py` + `epic_pipeline.py` + `epic_estimation.py`; stage Start/End from Jira Start dates + calc-days; Canvas display only (no `reports/` file); `fields.startDate`, `epicEstimation` JQL in config; tests `test_stage_dates.py`, `test_epic_pipeline.py`; skills/commands/WORKFLOW updated.
- 2026-06-05 — **Other = unmapped segments only:** `DEFAULT_SIDE_DISPLAY` + `resolve_side_display_map()` in `config.py`; `load_config()` merges built-in defaults when PyYAML absent (warns, does not block); `member_side_for_classification()` routes unmapped → Other, work → Backend/QA/Web/Mobile; executive-summary **Warnings** for config/consistency; tests in `test_config.py`; removed dead `stageMapping` / `leaveMappingRules` from em-config.
- 2026-06-05 — **Jira links always clickable:** `resolve_jira_site_url` derives site from issue payloads when config/CLI absent; `linkify_bare_issue_keys` safety-net on report and standup output.
- 2026-06-05 — **Prefix-only stage mapping:** pipe-segment rules in `stages.py` replace keyword `stageMapping` / `_qa_scoped_release_stage`; `{Web|App} | UAT | …` → UAT + **Product + Design** Teams plan row; `QA | {Web|App} | Pre-Prod|Prod testing|Final Testing | …` → Pre-Prod testing; `QA | BE | Final Testing | …` → Prod final testing; `QA | {Platform} | UAT …` → Stage testing; Ready for release stage removed; fixes VP-19936 false UAT; docs + tests updated.
- 2026-06-05 — **Jira links everywhere:** standup summary uses browse links; member Issues column lists all linked keys (no 4-key cap); golden test asserts no bare `VP-*` keys in report tables/lists; sprint-report skill updated.
- 2026-06-05 — **QA platform-scoped stages:** removed cross-platform Test planning (`qa_cross`, `qaCrossPlatform`, QA all-platforms table); QA titles require `QA | {App|Web|BE} | …`; Assessment/Test Planning → per-platform **QA Test Planning** row; Automation + default QA execution → Stage testing; dev Assessment row renamed **Tech Solutioning**; legacy `QA | Assessment` → unmapped + DQ flag.
- 2026-06-05 — **Workflow refactor:** 9 flat scripts → one `scripts/sprintkit/` package mirroring the 5-step process (`config`, `jira_model`, `teams`, `stages`, `sprint_window`, `normalize`, `schedule`, `delta`, `timeline`, `bugs`, `quality`, `pipeline`, `render/*`) behind a single `scripts/sprint_report.py`. Consolidated to one `/sprint-report` command + one `sprint-analyst` agent (retired `recalculate-schedule`/`daily-standup` commands, `em-orchestrator` agent + skill, `sprint-planning` skill; recalc/standup are now flags). Fixes: Bug fix effort reconciles `Backend/Web/Mobile/QA/Other/Total`; removed always-empty Start/End columns + dead date code; blank line before Unmapped sprint work; reconciled Teams-plan Tasks count. Added golden pipeline test; behaviour ported verbatim (report parity vs old scripts) before fixes.
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
