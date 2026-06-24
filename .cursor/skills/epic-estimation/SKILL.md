---
name: epic-estimation
description: >-
  Runbook for epic delivery estimation: fetch all issues under one Epic (no sprint
  filter), map platform/team/stage effort, compute stage Start/End dates, display in
  a Cursor Canvas beside chat. Use for /epic-estimation. Never writes a report file.
disable-model-invocation: true
---

# Epic Estimation

One agent (`sprint-analyst`) drives epic estimation. The pipeline (`scripts/epic_estimation.py` → `scripts/sprintkit/`) owns effort mapping and stage date math; never hand-compute dates in prose.

**Output:** Cursor Canvas beside chat only — **never** save under `reports/`.

## Protocol

```
PLAN → FETCH → RUN → DISPLAY
```

### PLAN

1. Read `.cursor/config/em-config.yaml`.
2. Require **Epic key** from the user (e.g. `VP-12345`).
3. Confirm `projectKey`; resolve `cloudId` via Atlassian MCP if empty.

### FETCH — epic issue tree (no sprint filter)

Follow `.cursor/skills/jira-domain/SKILL.md` epic-scope rules:

1. `getAccessibleAtlassianResources` when `cloudId` empty.
2. Discover Start date field if needed → `fields.startDate` in config.
3. **Pass 1** — `searchJiraIssuesUsingJql` with `epicEstimation.epicScopeJql` (substitute `{projectKey}`, `{epicKey}`).
4. **Pass 2** — fetch tasks/sub-tasks: `epicEstimation.taskScopeJql` with `{parentKeys}` = story keys from pass 1.
5. Fields: sprint fetch set **plus** `duedate`, `fields.startDate`.
6. Merge + dedupe → `scripts/.tmp/epic-{epicKey}-issues.json`.

### RUN

```bash
python scripts/epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}
```

Stdout is a single JSON object (`epicKey`, `deliveryStart`, `goLive`, `timeline`, `canvas`, `markdown`, `warnings`, `unmappedCount`). Optional `--tmp-dir scripts/.tmp` writes debug JSON only.

### DISPLAY

1. Parse stdout JSON.
2. Write/update `~/.cursor/projects/Users-easygautam-Documents-Sprint-Automation/canvases/epic-{epicKey}.canvas.tsx` — embed the `canvas` object inline (see canvas skill).
3. **Do not** call MCP `open_resource` to open the canvas — it can hang. Instead, include a markdown link to the `.canvas.tsx` file and tell the user to click it to open beside chat.
4. Brief chat summary: delivery start, go-live, unmapped count, top warnings.

**Do not** write `reports/*.md` or use `--output`.

## Stage date rules

| Stage | Start | End |
|-------|-------|-----|
| Tech Solutioning | Earliest Jira Start among stage tasks; none → `—` | `add_business_days(start, calculatedDays)` |
| Development | Earliest Jira Start among dev tasks; Web/Mobile ≥ BE dev end | same |
| Other stages | `next_workday(prior_stage_end)` when stage has tasks or effort; no tasks/effort → `—` | same |

Effort: `build_timeline_breakdown` (6h/day, Task/Sub-task only). Details: `delivery-flow` skill.

## Dry-run (no Jira)

Use fixture issues and pass `--jira-site-url https://example.atlassian.net`.

## Related skills

- `jira-domain` — hierarchy, epic JQL, Start date field
- `delivery-flow` — stage order, BE→Web/Mobile dependency
- `canvas` — canvas authoring rules
