# Sprint report

Run the EM sprint report through `.cursor/agents/sprint-analyst.md` (runbook: `.cursor/skills/sprint-report/SKILL.md`).

One pipeline (`scripts/sprint_report.py`) fetches → maps platform/team → maps leaves → maps stages → calculates effort, then renders all six deliverables into `reports/sprint-{DD-MM-YYYY}.md`. Summarize status counts (on_track / at_risk / delayed / blocked) in chat.

## Options

- **Recalculate** after a priority or scope change: add `--recalc` — snapshots the previous schedule and adds a **Schedule Delta** section. Ask the user for the change type (priority / add / remove / reassignment) if it is unclear.
- **Daily standup** (chat only, no file): add `--standup` — prints blockers, overdue, and at-risk items per assignee.
