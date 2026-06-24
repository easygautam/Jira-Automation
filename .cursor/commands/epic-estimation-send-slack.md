# Epic estimation → Slack

Run epic delivery estimation through `.cursor/agents/sprint-analyst.md` (runbook: `.cursor/skills/epic-estimation-send-slack/SKILL.md`).

Extends **`/epic-estimation`**: same Jira fetch, pipeline, and Cursor Canvas — then posts a Block Kit message to `#gautam-personal-agent`.

Requires **`SLACK_BOT_TOKEN`** — local: `.env.local` (copy from `.env.example`); cloud: [Cursor Cloud Agents Secrets](https://cursor.com/dashboard?tab=cloud-agents).

```bash
python scripts/epic_estimation_slack.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}
```

Use `--dry-run` to preview Block Kit JSON without posting. Use `--check-slack` to verify credentials.

Summarize delivery start, go-live, unmapped count, and the Slack permalink in chat after opening the canvas.
