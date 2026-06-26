# Epic estimation → Slack

Agent: **sprint-analyst** · Skill: `epic-estimation-send-slack` · Wrapper: `python scripts/run_epic_estimation_slack.py --epic {epicKey}`

Requires `SLACK_BOT_TOKEN` (`.env.local` or Cursor Cloud Secrets). One pipeline run: canvas + Slack + summary.
