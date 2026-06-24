# Epic estimation

Run epic delivery estimation through `.cursor/agents/sprint-analyst.md` (runbook: `.cursor/skills/epic-estimation/SKILL.md`).

Requires an **Epic key** (e.g. `ABC-12345`). Project is derived from the epic key — no `--project` needed.

**No report file is written** — unlike `/sprint-report`.

```bash
python scripts/epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Summarize delivery start, go-live, and unmapped count in chat after opening the canvas.
