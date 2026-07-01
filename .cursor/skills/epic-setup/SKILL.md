---
name: epic-setup
description: >-
  Plan and create delivery-stage Jira tasks for an epic using JIRA-BEST-PRACTICES
  pipe-prefix titles. Skips stages that already have mapped work. Use for /epic-setup.
  Dry-run by default; Jira writes require --create or explicit user confirmation.
disable-model-invocation: true
---

# Epic Setup

**Output:** Chat plan (existing / skipped / to-create). Optional Jira Task creates via MCP.

Title rules: [`docs/JIRA-BEST-PRACTICES.md`](../../docs/JIRA-BEST-PRACTICES.md). Stage detection: [`scripts/sprintkit/stages.py`](../../scripts/sprintkit/stages.py) `classify_issue`.

## Protocol

```
PLAN → FETCH → RUN → [CREATE] → REPORT
```

### PLAN

1. Read `.cursor/config/em-config.yaml`
2. Require **Epic key** (e.g. `PPL-1546`). Project derived from key.
3. Optional flags: `--platforms backend,mobile,frontend`, `--no-dev-placeholders`, `--create`

### FETCH

Follow `.cursor/skills/_shared/jira-fetch-epic.md`.

### RUN (dry-run default)

```bash
python scripts/run_epic_setup.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Paste stdout plan table. Do **not** create Jira issues unless user confirms or `--create` was passed.

With `--json` for structured plan:

```bash
python scripts/run_epic_setup.py --epic {epicKey} --issues scripts/.tmp/epic-{epicKey}-issues.json --json
```

### CREATE (only on confirm or `--create`)

Re-run with `--create` to print MCP payloads, then call `createJiraIssue` for each `toCreate` entry:

```bash
python scripts/run_epic_setup.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --create
```

For each payload block:

- `cloudId` from config `jira.cloudId` (resolve via `getAccessibleAtlassianResources` if empty)
- `projectKey`, `issueTypeName`, `summary`, `parent`, `additional_fields` from payload
- **Never** edit or delete existing issues
- **Never** create a task when `(platform, stage)` is already covered

### REPORT

- List created issue keys with links (`jira.siteUrl`)
- If nothing to create, state epic already has requested stages
- Suggest `/epic-estimation` for timeline canvas

## Duplicate rule

If any Task/Sub-task on the epic classifies to `(platform, stage)` via `classify_issue` with `kind == "work"`, skip that stage. One Development task per platform is sufficient (feature tasks count).

## Stages templated

| Platform | Stages created |
|----------|----------------|
| backend | Tech Solutioning, QA Test Planning, Development, Stage testing, Prod release, Prod final testing |
| mobile / frontend | Tech Solutioning, QA Test Planning, Development, Stage testing, Pre-Prod testing, UAT |

**Not created:** Bug fixes, Stage final testing, Go live, Ready for Release (synthetic buffers / status).

## Jira writes

This command **overrides** default read-only Jira rule when the user runs `/epic-setup` with confirmation or `--create`.

## Dry-run (no Jira)

Use a minimal issues JSON with epic key only, or fixture under `scripts/tests/fixtures/`.

## Related

- `jira-domain` — epic fetch JQL
- `delivery-flow` — execution stage order
- `/epic-estimation` — stage dates after tasks exist
