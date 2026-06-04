---
name: jira-domain
description: >-
  Jira issue hierarchy, effort rollup, and priority rules for EM sprint workflow.
  Use when fetching Jira data, rolling up estimates, or interpreting Epic/Story/Task
  relationships for sprint planning and reports.
disable-model-invocation: true
---

# Jira Domain

## Hierarchy

Epic (priority source) → Story → Task / Sub-task (estimate + assignee). Walk `parent` until Epic.

| Type | Role |
|------|------|
| Epic | Delivery item (PRD) |
| Story | Independently releasable slice |
| Task / Sub-task | Execution; estimates on `timeoriginalestimate`, summed per assignee per story |
| Bug | Schedulable via `effective_estimate_seconds` (`timespent` if &gt; 0, else OE); **Bug fix effort** report uses `timespent` only; **DQ:** bugs in active statuses (`dataQuality.bugActiveStatuses`) skip time flags; `bugNoWorklogStatuses` (e.g. Not a Bug) skip worklog checks; other bugs must have worklog or get `Missing logged time` |

Task effective priority = Epic priority (`priorityOrder` in config). Flag missing estimates before scheduling.

## JQL (substitute `{projectKey}`)

```jql
project = {projectKey} AND sprint in openSprints()
project = {projectKey} AND issuetype = Epic AND sprint in openSprints()
parent = STORY-KEY
project = {projectKey} AND sprint in openSprints() AND timeoriginalestimate is EMPTY AND assignee is not EMPTY AND issuetype in (Task, Sub-task)
```

## MCP fetch

1. `getAccessibleAtlassianResources` if `cloudId` empty
2. Discover Sprint field via `getJiraIssueTypeMetaWithFields` if needed → `fields.sprint` in config
3. `searchJiraIssuesUsingJql` paginated (`maxResults=100`, `nextPageToken`)
4. Fields: `summary, status, assignee, priority, issuetype, parent, timeoriginalestimate, timespent, created, updated, resolutiondate, labels, components, {fields.sprint}, {fields.rank}` (see `fields` in config)
5. Write `scripts/.tmp/issues.json` → `sprint_meta.py` → `sprint-meta.json` (do not infer sprint dates)

## Leave tasks (timeline)

Leave tasks: summary starts with `Leave |` (see `timeline.leaveTaskPrefixes`). `Leave | Planned` → planned leave; `Leave | Unplanned` → unplanned delay; other `Leave | <reason>` (e.g. `Leave | Health Issue`) → planned leave. Team comes from assignee’s other tasks on the same epic when the title has no BE/QA/WEB prefix.

## Team from summary

First `|` segment only → `jira_teams.py` + `teamPrefixMapping` in config. Unmatched or no pipe → **Other**. QA on `QA | APP | …` is QA, not Mobile. Assessment tasks: `{prefix} | Assessment` → platform Assessment; `QA | Assessment` → cross-platform test planning. `qa_platform_stream()` scopes `QA | Web/Mobile/BE` to frontend/mobile/backend. Full alias list lives in config, not duplicated here.
