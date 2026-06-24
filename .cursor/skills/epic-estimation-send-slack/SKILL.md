---
name: epic-estimation-send-slack
description: >-
  Runbook for epic delivery estimation with Slack post: same as epic-estimation
  (fetch, pipeline, Cursor Canvas) then post Block Kit message to Slack.
  Use for /epic-estimation-send-slack. Never writes a report file.
disable-model-invocation: true
---

# Epic Estimation → Slack

Extends **epic-estimation**. One agent (`sprint-analyst`) drives the flow. The pipeline owns effort mapping and stage date math; never hand-compute dates in prose.

**Output:** Cursor Canvas beside chat **plus** Slack Block Kit post to `#gautam-personal-agent` — **never** save under `reports/`.

## Protocol

```
PLAN → FETCH → RUN → DISPLAY → SLACK
```

### PLAN

Same as `.cursor/skills/epic-estimation/SKILL.md`:

1. Read `.cursor/config/em-config.yaml`.
2. Require **Epic key** from the user (e.g. `ABC-12345`). Project is derived from the epic key — do not ask for project.
3. Resolve `cloudId` via Atlassian MCP if empty.
4. Confirm Slack credentials: local `.env.local` or Cursor Cloud Secrets (`SLACK_BOT_TOKEN`; optional `SLACK_CHANNEL_ID`).

### FETCH — epic issue tree (no sprint filter)

Follow `.cursor/skills/jira-domain/SKILL.md` epic-scope rules (identical to epic-estimation).

### RUN

Same CLI as epic-estimation:

```bash
python scripts/epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Stdout JSON includes `canvas`, `markdown`, `timeline`, etc.

### DISPLAY

Same as epic-estimation:

1. Parse stdout JSON.
2. Write/update `~/.cursor/projects/Users-easygautam-Documents-Sprint-Automation/canvases/epic-{epicKey}.canvas.tsx` — embed the `canvas` object inline (see canvas skill).
3. **Do not** call MCP `open_resource` to open the canvas — it can hang. Instead, include a markdown link to the `.canvas.tsx` file and tell the user to click it to open beside chat.

### SLACK

Post Block Kit message built from the `canvas` JSON:

```bash
python scripts/epic_estimation_slack.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

- On success, stdout JSON includes `slack.posted`, `slack.permalink`, `slack.channel`.
- Use `--dry-run` to preview Block Kit payload without posting.
- If native table blocks are rejected by the workspace, the client automatically falls back to monospace tables.

**Do not** write `reports/*.md` or use `--output`.

## Slack prerequisites

### Local (Cursor desktop / terminal)

1. Create Slack app with bot scopes: `chat:write`, `channels:read` (+ `groups:read` if channel is private).
2. Install app to workspace; invite bot to `#gautam-personal-agent`.
3. Copy [`.env.example`](../../.env.example) → `.env.local` and set `SLACK_BOT_TOKEN=xoxb-…`
4. Optional: set `SLACK_CHANNEL_ID=C…` in `.env.local` (or `slack.channelId` in em-config.yaml) to skip channel lookup.

Verify setup:

```bash
python scripts/epic_estimation_slack.py --check-slack \
  --config .cursor/config/em-config.yaml
```

### Cursor Cloud Agents

Cloud agents do **not** read your laptop shell profile. Add secrets in **[Cursor Dashboard → Cloud Agents → Secrets](https://cursor.com/dashboard?tab=cloud-agents)**:

| Secret name | Type | Purpose |
|-------------|------|---------|
| `SLACK_BOT_TOKEN` | **Runtime Secret** | Bot token (`xoxb-…`) — never commit |
| `SLACK_CHANNEL_ID` | Environment Variable | Optional channel ID (`C…`) — faster, no `channels:read` lookup |

Repo includes [`.cursor/environment.json`](../../environment.json) with `pip install -r requirements.txt` so cloud agents load full `em-config.yaml`.

After adding secrets, restart the cloud agent or re-run `--check-slack` to confirm.

Channel name fallback is configured in `em-config.yaml` under `slack.channel`.

## Stage date rules

Same as epic-estimation — see `.cursor/skills/delivery-flow/SKILL.md` and `stage_dates.py`.

## Related skills

- `epic-estimation` — base fetch, pipeline, canvas display
- `jira-domain` — hierarchy, epic JQL, Start date field
- `delivery-flow` — stage order, BE→Web/Mobile dependency
- `canvas` — canvas authoring rules
