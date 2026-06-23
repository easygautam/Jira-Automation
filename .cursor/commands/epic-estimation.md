# Epic estimation

Run epic delivery estimation through `.cursor/agents/sprint-analyst.md` (runbook: `.cursor/skills/epic-estimation/SKILL.md`).

Requires an **Epic key** (e.g. `VP-12345`). Fetches the full epic issue tree (no sprint filter), maps effort by platform/team/stage, computes stage Start/End dates, and **displays results in a Cursor Canvas beside chat**.

**No report file is written** — unlike `/sprint-report`.

```bash
python scripts/epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}
```

Summarize delivery start, go-live, and unmapped count in chat after opening the canvas.
