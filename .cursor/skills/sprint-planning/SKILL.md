---
name: sprint-planning
description: >-
  Sprint task planning, schedule calculation, and re-priority recalculation for EM
  workflow. Use for /recalculate-schedule, effort-based start/due dates, or when
  priority or sprint scope changes.
disable-model-invocation: true
---

# Sprint Planning

## Task planning phases

1. **Assign** — tasks assigned to team in sprint
2. **Assess** — team adds Original Estimation on tasks/subtasks
3. **Schedule** — once efforts exist, calculate start and due date per item to find completion date

## Status tracking

Daily morning scrum: discuss task status, delays, challenges, blockers. Use `/daily-standup` for prep.

## Task re-priority

When priority changes, or items added/removed from sprint:

1. Re-fetch sprint issues from Jira
2. Snapshot prior schedule: `cp scripts/.tmp/schedule.json scripts/.tmp/prior-schedule.json`
3. Rebuild per-assignee priority queues (`jira_normalize.py`)
4. Re-run `scripts/schedule_engine.py`
5. Generate report with **Schedule Delta** (`scripts/schedule_delta.py` diffs prior vs current schedule JSON)

Example: sprint has tasks T1…Tn; member M1 has efforts and T1 start S1, due D1. Epic priority changes → re-sort M1 queue → cascade new start/due for T1 and all following tasks.

## Priority queue (per assignee)

Sort order (ascending = scheduled first):

1. Epic priority rank (`epicPriorityRank`)
2. Story rank (`storyRank`)
3. Created date (tie-break)

## Schedule engine I/O

**Do not calculate dates in the agent.** Run:

```bash
python scripts/jira_normalize.py --config .cursor/config/em-config.yaml \
  --input issues.json --output engine-input.json \
  --sprint-meta scripts/.tmp/sprint-meta.json
python scripts/schedule_engine.py engine-input.json
```

Sprint dates come from `sprint-meta.json` (Jira active sprint field). Manual `--sprint-start/end` only as override.

### Input schema

```json
{
  "sprintStart": "YYYY-MM-DD",
  "sprintEnd": "YYYY-MM-DD",
  "hoursPerDay": 8,
  "workingDays": [0, 1, 2, 3, 4],
  "today": "YYYY-MM-DD",
  "items": [
    {
      "key": "PROJ-12",
      "storyKey": "PROJ-10",
      "epicKey": "PROJ-1",
      "assignee": "alice",
      "estimateSeconds": 28800,
      "epicPriorityRank": 1,
      "storyRank": 2,
      "team": "backend",
      "created": "2026-06-01T10:00:00.000Z",
      "blocked": false,
      "dependencies": [
        { "type": "backend_delivery", "dependsOnKey": "PROJ-50", "epicKey": "PROJ-1" }
      ]
    }
  ]
}
```

### Output schema

```json
{
  "scheduled": [
    {
      "key": "PROJ-12",
      "storyKey": "PROJ-10",
      "epicKey": "PROJ-1",
      "assignee": "alice",
      "startDate": "2026-06-02",
      "dueDate": "2026-06-03",
      "durationDays": 2,
      "status": "on_track",
      "dependencyNotes": []
    }
  ],
  "violations": [],
  "unscheduled": [{ "key": "PROJ-99", "reason": "missing_estimate" }]
}
```

`violations` is always empty: unscheduled dependencies are not flagged. BE→Mobile/Web start order applies only when the dependency task is already scheduled.

Duration, dependencies, and status rules: `.cursor/rules/schedule-engine.mdc` and `scripts/schedule_engine.py`.

## Re-priority checklist

- [ ] Identify change type: priority / add / remove / reassignment
- [ ] Re-normalize Jira JSON
- [ ] Re-run schedule engine
- [ ] Compare to previous report
- [ ] Save new report with delta section
