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

## Epic rollup (delivery items)

- **Start** = earliest child task `startDate`; **Due** = latest child `dueDate`
- **Status** = worst child (blocked > delayed > at_risk > on_track); **TBD** if unscheduled

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
