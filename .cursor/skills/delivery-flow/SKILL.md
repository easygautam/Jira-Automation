---
name: delivery-flow
description: >-
  Delivery pipeline phases, tech assessment outcomes, and cross-team dependencies
  for EM scheduling. Use when mapping Jira status to phases or applying BE/Mobile/Web/QA
  dependency rules in sprint reports.
disable-model-invocation: true
---

# Delivery Flow

## Complete flow of a delivery

```
PRD Tech Discussion
  → Tech Assessment
  → Development
  → QA Testing
  → Bug fixes
  → QA final testing
  → Pre-Prod Deployments
  → QA Pre-Prod Testing
  → Product UAT and Design Review
  → Ready for Release
```

Map Jira statuses via `statusPhaseMap` in `.cursor/config/em-config.yaml`.

## Tech assessment detail definition

All teams (Backend, Mobile, Web, QA) understand the requirement and do tech solutioning; they prepare tasks and efforts.

| Team | Outcome |
|------|---------|
| Backend, Frontend, Mobile | Engineering requirements document — high level and low level design; early challenges discussed with product |
| QA | Test cases and automation testing solution; challenges highlighted to tech team |

## Dependencies in the delivery flow

| Dependency | Scheduling rule |
|------------|-----------------|
| Backend provides API contracts | Mobile and Web use contracts during development |
| Backend delivers APIs | Mobile/Web start after BE due date (schedule engine) |
| Backend provides API contracts | QA writes automation |
| Backend delivers APIs | QA validates API once backend delivers |

Engine implementation (`scripts/sprintkit/schedule.py`):

- Items with `team` = mobile or frontend: `start ≥` linked BE story/item due date for same epic
- Items with `team` = qa and dependency type API validation: start ≥ BE due date for same epic

Pass dependencies in normalized JSON as:

```json
{ "type": "backend_delivery", "dependsOnKey": "PROJ-50", "epicKey": "PROJ-1" }
```

If the dependency task is not scheduled (e.g. missing estimate), the engine does **not** flag a violation and does not delay the dependent task.

## Phase snapshot (for reports)

For each Epic, derive current phase from highest child status in pipeline order, or epic status if no children.

## Execution stages (sprint report timeline)

Per-epic **Execution stages** tables are **per platform** (`timeline.executionStages` in config). Platforms run on independent planned dates.

| Platform | Stage order (summary) |
|----------|------------------------|
| Backend | Tech Solutioning → QA Test Planning → Development → Stage testing → Bug fixes (10% of dev) → Stage final testing (10% of stage testing) → Prod release → Prod final testing → Go live date |
| Web / Mobile | Tech Solutioning → QA Test Planning → Development → Stage testing → Bug fixes → Stage final testing → Pre-Prod testing → UAT → Go live date |

**Jira mapping highlights (pipe-segment only):**

- `{BE\|Web\|App} \| Assessment` → platform **Tech Solutioning**
- `QA \| {App\|Web\|BE} \| Assessment` (or Test Planning in title) → **QA Test Planning** on that platform only
- `QA \| {Platform} \| Automation \| …` → Stage testing on that platform
- `QA \| {Web\|App} \| Pre-Prod\|Pre-Prod Testing\|Final Testing\|Prod testing \| …` → **Pre-Prod testing**
- `QA \| BE \| Final Testing \| …` → **Prod final testing** (backend; not Pre-Prod)
- `{Web\|App} \| UAT \| …` → **UAT** (Teams plan: **Product + Design**); `QA \| {Platform} \| UAT …` → Stage testing (QA does not own UAT)
- Other `QA \| {Platform} \| …` → Stage testing
- `QA \| …` without platform segment → unmapped + data-quality flag
- Pipe-prefix dev tasks → Development; buffers in `timeline.effortBuffers`

**Team on tasks:** first `|` prefix via `scripts/sprintkit/teams.py` + stage mapping in `scripts/sprintkit/stages.py` (see `jira-domain`). Timeline effort counts **Task/Sub-task** only; **Bug** effort is a separate report section (worklog). Timeline does not bucket Bug issue types.

## Epic estimation stage dates (`/epic-estimation`)

Computed in `scripts/sprintkit/stage_dates.py` after timeline effort aggregation. Displayed in a Cursor Canvas (no sprint report file).

| Stage | Start | End |
|-------|-------|-----|
| Tech Solutioning | Earliest Jira **Start date** among stage tasks; none → `—` | `add_business_days(start, calculatedDays)` (6h calc days) |
| Development | Earliest Jira Start among dev tasks; Web/Mobile ≥ next workday after BE Development end | same |
| Other stages | `next_workday(prior_stage_end)` when stage has tasks or effort; **no tasks and no effort → `—`** | same |

Epic rollup: **deliveryStart** = earliest resolved stage start; **goLive** = Go live date stage end (or latest stage end). Working days: `scheduling.workingDayInts` (Mon–Fri).
