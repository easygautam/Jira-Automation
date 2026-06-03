---
name: sprint-report
description: >-
  Generate sprint health reports with on-track/delayed analysis and calculated
  start/due dates. Use for /sprint-report, /daily-standup, or after schedule
  recalculation.
disable-model-invocation: true
---

# Sprint Report

## Workflow

1. Run `.cursor/skills/em-orchestrator/SKILL.md` through REPORT
2. Save `reports/sprint-{YYYY-MM-DD}.md`; summarize on_track / at_risk / delayed / blocked in chat

Report shape and sections are produced by `scripts/render_report.py` (not hand-authored markdown). Status rules: `.cursor/rules/schedule-engine.mdc`.

## Bug fix effort

- Summary table: all sprint epics — Epic ID, Epic Name, Backend, Web, Mobile, Bugs (worklog hours; — when none)
- Per-epic member tables: Member, Bug effort (h), Bug count (no team column)

## Team tasks plan

- Per-assignee scheduled task tables (Key, Task title, Epic, Effort, Status); replaces former Schedule by assignee index

## Data quality flags

- Reason summary table at section top; one row per ticket (multiple reasons joined with `;`)
- Tasks/sub-tasks: `Missing estimates` when Original Estimate empty
- Bugs in To Do / In Progress / Hold / Deferred: no time-related flag
- Bugs in Not a Bug (config: `bugNoWorklogStatuses`): no worklog flag
- Other resolved bugs need worklog or get `Missing logged time`
- Recommended actions split task estimates vs bug worklog counts

## Schedule Delta (recalculate)

When `scripts/.tmp/prior-schedule.json` exists, report includes date/status changes vs current schedule.

## Epic rollup (delivery items)

- **Start** = earliest child task `startDate`; **Due** = latest child `dueDate`
- **Status** = worst child (blocked > delayed > at_risk > on_track); **TBD** if unscheduled
- **Sort:** Jira **Rank** field (LexoRank / board drag-and-drop order; `fields.rank` in config)
- **Title** links to that epic's PRD block in Timeline breakdown (`#prd-{epicKey}`) when timeline data exists

## Standup mode (`/daily-standup`)

Same pipeline; shorter chat output (blockers, overdue, due today, talking points per assignee).

## Dry-run (no Jira)

```bash
python scripts/sprint_meta.py --input scripts/fixtures/sample_issues_with_sprint.json --output scripts/.tmp/sprint-meta.json
python scripts/jira_normalize.py --input scripts/fixtures/sample_issues.json --sprint-meta scripts/.tmp/sprint-meta.json --output scripts/.tmp/engine-input.json
python scripts/schedule_engine.py scripts/.tmp/engine-input.json > scripts/.tmp/schedule.json
python scripts/timeline_breakdown.py --issues scripts/fixtures/sample_issues.json --schedule scripts/.tmp/schedule.json --output scripts/.tmp/timeline-breakdown.json
python scripts/bug_effort_breakdown.py --issues scripts/fixtures/sample_issues.json --schedule scripts/.tmp/schedule.json --output scripts/.tmp/bug-effort-breakdown.json
python scripts/render_report.py --sprint-meta scripts/.tmp/sprint-meta.json --timeline-breakdown scripts/.tmp/timeline-breakdown.json --bug-breakdown scripts/.tmp/bug-effort-breakdown.json
```
