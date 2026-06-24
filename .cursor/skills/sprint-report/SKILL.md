---
name: sprint-report
description: >-
  Runbook for the EM sprint report: fetch Jira sprint data and run the single
  sprint_report pipeline that maps platform/team, leaves, and stages, calculates
  team effort, and renders six deliverables. Use for /sprint-report, recalculation
  (Schedule Delta), daily standup, or sprint health questions.
disable-model-invocation: true
---

# Sprint Report

One agent (`sprint-analyst`) and one command (`/sprint-report`) drive the whole workflow. The pipeline (`scripts/sprint_report.py` → `scripts/sprintkit/`) owns all mapping and date math; never hand-author report markdown or compute dates in prose.

## Protocol

```
PLAN → FETCH (Load) → RUN (map + calculate + render) → REPORT
```

### PLAN

1. Read `.cursor/config/em-config.yaml`.
2. Resolve **project key** for sprint fetch: user-stated project in chat → `--project` CLI → `jira.projectKey` in config → ask the user if still empty.
3. Resolve `cloudId` via Atlassian MCP if empty.
4. Pick mode: full report | `--recalc` (Schedule Delta) | `--standup` (chat only). If recalculating and the change is unknown, ask: priority / add / remove / reassignment.

### FETCH — Step 1 (Load sprint items)

Follow `.cursor/skills/jira-domain/SKILL.md`:

1. `getAccessibleAtlassianResources` when `cloudId` empty.
2. Discover the Sprint field (`getJiraIssueTypeMetaWithFields`) if needed → `fields.sprint` in config.
3. `searchJiraIssuesUsingJql` with the sprint JQL (substitute `{projectKey}`); include `fields.sprint` and `fields.rank`.
4. Paginate until all issues are fetched.
5. Write raw issues to `scripts/.tmp/issues.json`.

The active sprint window is derived from the Jira sprint field inside the pipeline (`scripts/sprintkit/sprint_window.py`) — do not infer sprint dates.

### RUN — Steps 2–5 + render

A single command maps each task to platform/team (Step 2), maps leave tasks (Step 3), maps each task to a stage (Step 4), calculates team effort per stage (Step 5), and renders the six deliverables:

```bash
python scripts/sprint_report.py \
  --issues scripts/.tmp/issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}   # optional when jira.projectKey is set in config
```

The command writes `reports/sprint-{YYYY-MM-DD}.md` and prints a JSON summary (status counts, scheduled/unscheduled, sprint window). It also snapshots pipeline JSON under `scripts/.tmp/` (`sprint-meta`, `engine-input`, `schedule`, `timeline-breakdown`, `bug-effort-breakdown`) for debugging and recalculation continuity.

**Options**

| Flag | Effect |
|------|--------|
| `--recalc` | Snapshot the existing `scripts/.tmp/schedule.json` as `prior-schedule.json` and add a **Schedule Delta** section |
| `--prior-schedule PATH` | Use an explicit prior schedule for the delta |
| `--standup` | Print a short standup summary to chat (blockers, overdue, at-risk); report saved only with `--output` |
| `--sprint-start / --sprint-end` | Manual sprint-window override when the Jira field is unavailable |
| `--today YYYY-MM-DD` | Deterministic "today" for reproducible runs |
| `--output PATH` | Override the report path |

### REPORT

Summarize on_track / at_risk / delayed / blocked in chat and link the saved report. Status rules: `.cursor/rules/schedule-engine.mdc`.

## Six deliverables (report order)

Executive summary → **Delivery items (Epics)** → **Teams plan** → **Member breakdown** → **Execution stages** → **Bug fix effort** → **Team tasks plan** → Data quality flags → Recommended actions (→ Schedule Delta when a prior snapshot exists).

- **Delivery items:** Start = earliest child `startDate`, Due = latest child `dueDate`, Status = worst child (blocked > delayed > at_risk > on_track), TBD if unscheduled. Sorted by Jira **Rank** (LexoRank / board order, `fields.rank`). Title links to the epic's PRD block in Timeline breakdown (`#prd-{epicKey}`).
- **Teams plan / Member breakdown / Execution stages:** effort is **Task + Sub-task only** (bugs excluded), 6h/day (`timeline.hoursPerDay`). `Calc days = (Efforts + Leave) / (Resources × 6h)` as decimal person-days (e.g. 3h → 0.5). Stage/member `Leave (h)` combines planned + unplanned. Platforms with no Jira tasks are omitted. Calendar dates are **deferred** — there are no Start/End columns (sprint-window date rule to be added later).
- **Bug fix effort:** Jira **Bug** issues, worklog **time spent**; columns Backend / Web / Mobile / QA / Other / **Total** / Bugs — each bug counts once on its team's side and the columns reconcile to Total. Per-epic member tables (Member, Bug effort, Bug count).
- **Team tasks plan:** per-assignee scheduled tasks (Key, Task title, Epic, Effort, Status); dates are engine-calculated.
- **Data quality flags:** reason summary table + one consolidated row per ticket. Tasks/sub-tasks flag `Missing estimates`; bugs in active statuses (`dataQuality.bugActiveStatuses`) skip time flags; `bugNoWorklogStatuses` (Not a Bug) skip worklog checks; other resolved bugs need worklog or get `Missing logged time`.
- **Jira links:** every issue key renders as a browse link from `jira.siteUrl` (or `--jira-site-url`) — Delivery items, Timeline (headings, Issues column, unmapped), Bug fix effort, Team tasks plan, Data quality, Schedule Delta, and `--standup` output. Member **Issues** lists all keys (no truncation). When summarizing sprint health in chat, link keys the same way (`[VP-123]({siteUrl}/browse/VP-123)`).

## Schedule engine I/O (per assignee)

Sort order (scheduled first): epic priority rank → story rank → created date. On **recalculate**, the priority change re-sorts the member's queue and cascades new start/due dates for that task and all following tasks.

Input items carry `key, storyKey, epicKey, assignee, estimateSeconds, epicPriorityRank, storyRank, team, created, blocked, dependencies[]`. Output: `scheduled[] (startDate, dueDate, durationDays, status)`, `violations` (always empty — unscheduled dependencies are not flagged), `unscheduled[] (reason)`. Duration/dependency/status rules: `.cursor/rules/schedule-engine.mdc` and `scripts/sprintkit/schedule.py`.

## Dry-run (no Jira)

```bash
python scripts/sprint_report.py \
  --issues scripts/tests/fixtures/mini_issues.json \
  --project VP --today 2026-06-05 \
  --jira-site-url https://example.atlassian.net \
  --output /tmp/sprint-dry-run.md
```

## Error handling

| Condition | Action |
|-----------|--------|
| MCP auth failure | Prompt the user to authenticate the Atlassian plugin |
| Empty sprint | Report "no issues" with the JQL used |
| Sprint window unresolved | Re-fetch including the sprint field, or pass `--sprint-start/--sprint-end` |
| All unscheduled | List keys with missing estimates from the JSON summary |

## Related skills

- `jira-domain` — hierarchy, JQL, MCP fetch, team-from-summary
- `delivery-flow` — phases, execution stages, dependencies
