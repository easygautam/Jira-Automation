---
name: em-orchestrator
description: >-
  Engineering Manager workflow orchestrator. Coordinates Jira fetch, schedule
  calculation, and report generation. Use for /sprint-report, /recalculate-schedule,
  /daily-standup, or sprint health questions.
disable-model-invocation: true
---

# EM Orchestrator

## Protocol

```
PLAN → FETCH → NORMALIZE → CALCULATE → TIMELINE_BREAKDOWN → BUG_EFFORT → REPORT → SAVE
```

### PLAN

1. Read `.cursor/config/em-config.yaml`
2. Confirm `projectKey`; resolve `cloudId` if empty
3. Determine mode: full report | recalculate | standup
4. If recalculate and change unknown, ask: priority / add / remove / reassignment

### FETCH

Follow `.cursor/skills/jira-domain/SKILL.md`:

1. `getAccessibleAtlassianResources` when `cloudId` empty
2. Discover Sprint field if needed (`getJiraIssueTypeMetaWithFields`)
3. `searchJiraIssuesUsingJql` with sprint JQL (substitute `{projectKey}`) — include `fields.sprint`
4. Paginate until all issues fetched
5. Write raw issues to `scripts/.tmp/issues.json`
6. Extract sprint window:

```bash
python scripts/sprint_meta.py \
  --config .cursor/config/em-config.yaml \
  --input scripts/.tmp/issues.json \
  --output scripts/.tmp/sprint-meta.json
```

### NORMALIZE

```bash
python scripts/jira_normalize.py \
  --config .cursor/config/em-config.yaml \
  --input scripts/.tmp/issues.json \
  --output scripts/.tmp/engine-input.json \
  --sprint-meta scripts/.tmp/sprint-meta.json
```

Sprint dates come from `sprint-meta.json` (Jira active sprint). Use `--sprint-start/end` only as manual override if meta fails.

### CALCULATE

```bash
python scripts/schedule_engine.py scripts/.tmp/engine-input.json > scripts/.tmp/schedule.json
```

### TIMELINE_BREAKDOWN

After schedule calculation (uses 6h/day from `timeline.hoursPerDay`, separate from engine 8h). **Effort = Task + Sub-task only** (bugs excluded):

```bash
python scripts/timeline_breakdown.py \
  --config .cursor/config/em-config.yaml \
  --issues scripts/.tmp/issues.json \
  --schedule scripts/.tmp/schedule.json \
  --engine-input scripts/.tmp/engine-input.json \
  --output scripts/.tmp/timeline-breakdown.json
```

### BUG_EFFORT

Build bug effort JSON (embedded in sprint report — not a separate markdown file). Jira **Bug** issue type only; team from `jira_teams.py`:

```bash
python scripts/bug_effort_breakdown.py \
  --config .cursor/config/em-config.yaml \
  --issues scripts/.tmp/issues.json \
  --schedule scripts/.tmp/schedule.json \
  --output scripts/.tmp/bug-effort-breakdown.json
```

### REPORT

Follow `.cursor/skills/sprint-report/SKILL.md` template using schedule JSON + issue metadata.

```bash
python scripts/render_report.py \
  --issues scripts/.tmp/issues.json \
  --schedule scripts/.tmp/schedule.json \
  --engine-input scripts/.tmp/engine-input.json \
  --sprint-meta scripts/.tmp/sprint-meta.json \
  --timeline-breakdown scripts/.tmp/timeline-breakdown.json \
  --bug-breakdown scripts/.tmp/bug-effort-breakdown.json \
  --project {projectKey}
```

### SAVE

Write `reports/sprint-{YYYY-MM-DD}.md` per config `reporting.outputDir`.

## Error handling

| Condition | Action |
|-----------|--------|
| MCP auth failure | Prompt user to authenticate Atlassian plugin |
| Empty sprint | Report "no issues" with JQL used |
| All unscheduled | List keys with missing estimates |
| Prior report exists | Include Schedule Delta section (recalculate mode) |

## Subagent

For large sprints (>50 issues), dispatch `.cursor/agents/sprint-analyst.md` for FETCH + NORMALIZE only.

## Related skills

- `jira-domain` — hierarchy and JQL
- `delivery-flow` — phases and dependencies
- `sprint-planning` — engine I/O and re-priority
- `sprint-report` — markdown template
