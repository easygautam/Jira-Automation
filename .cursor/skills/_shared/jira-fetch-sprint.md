# Jira fetch — active sprint

Read-only MCP fetch. Jira write tools are forbidden unless the user explicitly overrides.

## Prerequisites

1. Load `.cursor/config/em-config.yaml`
2. Resolve `cloudId` via `getAccessibleAtlassianResources` if empty
3. Resolve project key: user-stated → `--project` → `jira.projectKey` → ask user

## Field discovery (when needed)

- Sprint field: `getJiraIssueTypeMetaWithFields` when `fields.sprint` is empty or `sprintDiscovery.autoDiscover` is true

## Fetch

1. `searchJiraIssuesUsingJql` with `jira.activeSprintJql` (substitute `{projectKey}`). Config JQL includes `issuetype in (Epic, Story, Task, Sub-task, Bug)` — do not fetch Test Execution or other types.
2. Paginate (`maxResults=100`, `nextPageToken`) until complete
3. Fields: `summary, status, assignee, priority, issuetype, parent, timeoriginalestimate, timespent, created, updated, resolutiondate, labels, components, duedate`, plus config `fields.sprint`, `fields.rank`, `fields.startDate`, `fields.teams`
4. Write merged issues to `scripts/.tmp/issues.json`

Do not infer sprint dates — the pipeline derives the active sprint window from the Jira sprint field.

## Reference

Hierarchy, JQL templates, team rules: `.cursor/skills/jira-domain/SKILL.md`
