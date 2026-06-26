---
name: epic-estimation-send-slack
description: >-
  Epic estimation + Slack Block Kit in one pipeline run. MCP fetch, then
  run_epic_estimation_slack wrapper. Never writes under reports/.
disable-model-invocation: true
---

# Epic Estimation → Slack

**Output:** Canvas + Slack post + chat summary — **never** `reports/`.

## Protocol

```
PLAN → FETCH → RUN → REPORT
```

### PLAN

1. Read `.cursor/config/em-config.yaml`
2. Require **Epic key** from user
3. Confirm Slack: `.env.local` or Cursor Cloud Secrets (`SLACK_BOT_TOKEN`; optional `SLACK_CHANNEL_ID`)

### FETCH

Follow `.cursor/skills/_shared/jira-fetch-epic.md`.

### RUN

One command — pipeline, canvas, and Slack:

```bash
python scripts/run_epic_estimation_slack.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Options on low-level CLI: `--dry-run`, `--check-slack`, `--write-canvas [PATH]`.

### REPORT

Follow `.cursor/skills/_shared/post-run.md` — include Slack permalink from summary when posted.

## Related

- `epic-estimation` skill — same fetch and canvas rules
- `.env.example` — local Slack setup
