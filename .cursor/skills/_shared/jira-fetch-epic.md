# Jira fetch — epic scope (no sprint filter)

Read-only MCP fetch. Requires **Epic key** from the user (project derived from key — do not ask for project).

## Prerequisites

1. Load `.cursor/config/em-config.yaml`
2. Resolve `cloudId` via `getAccessibleAtlassianResources` if empty
3. Discover Start date field if needed → `fields.startDate`

## Three-pass fetch

Substitute `{epicKey}` only (no project filter). JQL templates in config already include the issue-type allowlist (`issuetype in (Epic, Story, Task, Sub-task, Bug)`). Do not fetch Test Execution or other QA-only types.

| Pass | JQL template (config key) |
|------|---------------------------|
| 1 | `epicEstimation.epicScopeJql` |
| 2 | `epicEstimation.taskScopeJql` — `{parentKeys}` = story keys from pass 1 |
| 3 | `epicEstimation.subtaskScopeJql` — `{taskKeys}` = Task keys from passes 1–2 |

Fields: sprint fetch set plus `duedate`, `fields.startDate`, `fields.teams`.

Write merged + deduped issues to `scripts/.tmp/epic-{epicKey}-issues.json`.

## Reference

`.cursor/skills/jira-domain/SKILL.md`
