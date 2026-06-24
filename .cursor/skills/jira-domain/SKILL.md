---
name: jira-domain
description: >-
  Jira issue hierarchy, effort rollup, and priority rules for EM sprint workflow.
  Use when fetching Jira data, rolling up estimates, or interpreting Epic/Story/Task
  relationships for sprint planning and reports.
disable-model-invocation: true
---

# Jira Domain

## Team Jira guide

Human-readable naming and estimate rules: [`docs/JIRA-BEST-PRACTICES.md`](../../docs/JIRA-BEST-PRACTICES.md).

## Hierarchy

Epic (priority source) → Story → Task / Sub-task (estimate + assignee). Walk `parent` until Epic.

| Type | Role |
|------|------|
| Epic | Delivery item (PRD) |
| Story | Independently releasable slice |
| Task / Sub-task | Execution; estimates on `timeoriginalestimate`, summed per assignee per story |
| Bug | Schedulable via `effective_estimate_seconds` (`timespent` if &gt; 0, else OE); **Bug fix effort** report uses `timespent` only; **DQ:** bugs in active statuses (`dataQuality.bugActiveStatuses`) skip time flags; `bugNoWorklogStatuses` (e.g. Not a Bug) skip worklog checks; other bugs must have worklog or get `Missing logged time` |

Task effective priority = Epic priority (`priorityOrder` in config). Flag missing estimates before scheduling.

## JQL — sprint report (substitute `{projectKey}`)

```jql
project = {projectKey} AND sprint in openSprints()
project = {projectKey} AND issuetype = Epic AND sprint in openSprints()
parent = STORY-KEY
project = {projectKey} AND sprint in openSprints() AND timeoriginalestimate is EMPTY AND assignee is not EMPTY AND issuetype in (Task, Sub-task)
```

Resolve `{projectKey}` from user-stated project → CLI `--project` → `jira.projectKey` in config.

## Epic scope JQL (`/epic-estimation`, substitute `{epicKey}` only)

Two-pass fetch (no sprint filter; no project filter — issue keys are site-wide unique):

```jql
# Pass 1 — epicEstimation.epicScopeJql
key = {epicKey} OR "Epic Link" = {epicKey} OR parent = {epicKey}

# Pass 2 — epicEstimation.taskScopeJql ({parentKeys} = story keys from pass 1)
parent in ({parentKeys})
```

Write merged issues to `scripts/.tmp/epic-{epicKey}-issues.json`. Include `fields.startDate` (`customfield_10015` by default), `duedate`, and `fields.teams` in MCP field list.

## MCP fetch (sprint)

1. `getAccessibleAtlassianResources` if `cloudId` empty
2. Discover Sprint field via `getJiraIssueTypeMetaWithFields` if needed → `fields.sprint` in config
3. `searchJiraIssuesUsingJql` paginated (`maxResults=100`, `nextPageToken`)
4. Fields: `summary, status, assignee, priority, issuetype, parent, timeoriginalestimate, timespent, created, updated, resolutiondate, labels, components, duedate, {fields.sprint}, {fields.rank}, {fields.startDate}, {fields.teams}` (see `fields` in config)
5. Write `scripts/.tmp/issues.json`; the pipeline derives the active sprint window (`scripts/sprintkit/sprint_window.py`) — do not infer sprint dates

## Leave tasks (timeline)

Leave tasks: summary starts with `Leave |` (see `timeline.leaveTaskPrefixes`). `Leave | Planned` → planned leave; `Leave | Unplanned` → unplanned delay; other `Leave | <reason>` (e.g. `Leave | Health Issue`) → planned leave. Team comes from assignee’s other tasks on the same epic when the title has no BE/QA/WEB prefix.

## Team resolution (title + Teams field)

**Primary:** first `|` segment → `scripts/sprintkit/teams.py` + `teamPrefixMapping` (built-in defaults in `sprintkit/config.py` when YAML is unavailable). **`DS |` / `DE |`** → Data Engineering (`data_engineering`, Backend delivery). **Title always wins** over the Jira field.

**Secondary:** Jira **Teams** select field (`fields.teams`, `teamFieldMapping`) when the title prefix is missing or unrecognized:

| Teams plan row | Jira field values | Delivery platform |
|----------------|-------------------|-------------------|
| Mobile | Android, IOS, KMM | Mobile |
| Backend | Admin, Backend | Backend |
| Data Engineering | Data Engineering | Backend (Development stage) |
| DevOps | DevOps | Backend (Development stage) |
| Web | Web | Web |
| QA | QA | platform from title when possible |
| Product + Design | Product, Analytics | UAT (frontend bucket) |
| Other | Other Teams, empty | unmapped |

Stage mapping remains **pipe-segment only** in `scripts/sprintkit/stages.py` (no keyword substring rules): `{BE|Web|App} | Assessment` → **Tech Solutioning**; `QA | {App|Web|BE} | Assessment` → **QA Test Planning**; `QA | {Platform} | Automation` → Stage testing; `{Web|App} | UAT | …` → **UAT** (Teams plan: **Product + Design**); field-only Product/Analytics → **UAT**; `QA | {Web|App} | Pre-Prod|Prod testing|Final Testing | …` → **Pre-Prod testing**; `QA | BE | Final Testing | …` → **Prod final testing**; `BE | Prod release |` / `BE | Prod final testing |` → backend release rows; pipe-prefix dev tasks → **Development**; field-resolved Mobile/Web/Backend → **Development**. QA without platform segment → unmapped.

## Teams plan — when **Other** appears

**Other** in the Teams plan member breakdown means **segment mapping failed** — not a catch-all for Backend/QA work.

| Goes to Backend / Web / Mobile / QA / Product + Design / Data Engineering / DevOps | Goes to **Other** only |
|--------------------------------------------------------|-------------------------|
| `BE \| …`, `WEB \| …`, `APP \| …` | No `\|` prefix and no Teams field, or unrecognized field value |
| `QA \| BE \| …`, `QA \| Web \| …`, `QA \| App \| …` | `QA \| …` without platform in segment 2 |
| `{Web\|App} \| UAT \| …` | Legacy `QA \| Assessment`; titles like `Stage-APP \| …` |
| Jira Teams field set (see team resolution above) | **Other Teams** field value with bad title |

Team row labels come from `resolve_side_display_map()` (`DEFAULT_SIDE_DISPLAY` + optional `timeline.sideDisplay` in config). Correctly prefixed tasks must **never** land under Other because of missing PyYAML or empty config.
