---
name: epic-estimation
description: >-
  Epic delivery estimation: MCP fetch, run_epic_estimation wrapper, scripted canvas.
  Use for /epic-estimation. Never writes under reports/.
disable-model-invocation: true
---

# Epic Estimation

**Output:** Cursor Canvas + chat summary — **never** `reports/`.

## Protocol

```
PLAN → FETCH → RUN → REPORT
```

### PLAN

1. Read `.cursor/config/em-config.yaml`
2. Require **Epic key** from user (e.g. `ABC-12345`). Project from epic key — do not ask for project.

### FETCH

Follow `.cursor/skills/_shared/jira-fetch-epic.md`.

### RUN

```bash
python scripts/run_epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Writes canvas via `--write-canvas` (default Cursor canvases dir). Prints `--summary-only` text.

Low-level CLI (debug): `scripts/epic_estimation.py` with `--write-canvas` and JSON stdout.

### REPORT

Follow `.cursor/skills/_shared/post-run.md`.

## Stage date rules

See `delivery-flow` skill and `scripts/sprintkit/stage_dates.py`.

## Dry-run (no Jira)

```bash
python scripts/run_epic_estimation.py \
  --epic VP-800 \
  --issues scripts/tests/fixtures/epic_cli_issues.json
```

(Use fixture path for `--issues`.)

## Related

- `jira-domain` — hierarchy, epic JQL
- `delivery-flow` — stage order, BE→Web/Mobile dependency
