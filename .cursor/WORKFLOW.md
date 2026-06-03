# EM workflow manifest

Canonical inventory for agents. **Runbook:** `.cursor/skills/em-orchestrator/SKILL.md`.

## Pipeline

`PLAN → FETCH → SPRINT_META → NORMALIZE → CALCULATE → TIMELINE_BREAKDOWN → BUG_EFFORT → REPORT → SAVE`

| Stage | Script | Output |
|-------|--------|--------|
| Sprint window | `sprint_meta.py` | `scripts/.tmp/sprint-meta.json` |
| Engine input | `jira_normalize.py` | `scripts/.tmp/engine-input.json` |
| Schedule (8h) | `schedule_engine.py` | `scripts/.tmp/schedule.json` |
| Timeline (6h, Task/Sub-task) | `timeline_breakdown.py` | `scripts/.tmp/timeline-breakdown.json` |
| Bug effort | `bug_effort_breakdown.py` | `scripts/.tmp/bug-effort-breakdown.json` |
| Report | `render_report.py` | `reports/sprint-{date}.md` |

Team prefixes: `scripts/jira_teams.py` + `em-config.yaml` `teamPrefixMapping` (first `|` segment only; else **Other**). Details: `jira-domain` skill.

## Config & entrypoints

- Config: `.cursor/config/em-config.yaml`
- Commands: `sprint-report`, `recalculate-schedule`, `daily-standup`, `improve-workflow` → matching skill under `.cursor/skills/`
- Rules: `em-workflow.mdc`, `schedule-engine.mdc`, `jira-read-only.mdc`
- Agent: `.cursor/agents/em-orchestrator.md` (subagent: `sprint-analyst.md` for large fetches)

## Scripts

`sprint_meta.py`, `jira_normalize.py`, `schedule_engine.py`, `timeline_breakdown.py`, `bug_effort_breakdown.py`, `render_report.py`, `jira_teams.py` — tests in `scripts/tests/`, fixtures in `scripts/fixtures/`.

## Report sections (order)

Executive summary → Delivery items (Epics) → Timeline breakdown (**Teams plan** = Backend/Web/Mobile/QA only; milestones in Task breakdown) → Bug fix effort → Schedule by assignee → Data quality (+ Schedule Delta on recalc).
