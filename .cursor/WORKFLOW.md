# EM workflow manifest

**Canonical inventory** — skills, rules, and agents link here. Do not duplicate command tables elsewhere.

## Command table

| Slash command | Agent | Skill | Wrapper (after MCP fetch) | Output |
|---------------|-------|-------|---------------------------|--------|
| `/sprint-report` | sprint-analyst | sprint-report | `python scripts/run_sprint_report.py` | `reports/sprint-{date}.md` + summary |
| `/sprint-report --recalc` | sprint-analyst | sprint-report | `run_sprint_report.py --recalc` | report + `prior-schedule.json` snapshot |
| `/sprint-report --standup` | sprint-analyst | sprint-report | `run_sprint_report.py --standup` | standup text only |
| `/epic-estimation` | sprint-analyst | epic-estimation | `python scripts/run_epic_estimation.py --epic {KEY}` | canvas `.tsx` + summary |
| `/epic-estimation-send-slack` | sprint-analyst | epic-estimation-send-slack | `python scripts/run_epic_estimation_slack.py --epic {KEY}` | canvas + Slack + summary |
| `/improve-workflow` | sprint-analyst | improve-workflow | (meta — no wrapper) | Improvement Report |

**Agent per run:** MCP FETCH (`_shared/jira-fetch-*.md`) → one wrapper script → paste (`_shared/post-run.md`).

## Three report deliverables

Executive summary → **Delivery items (Epics)** → **Epic Quality Report** (summary table only).

`--recalc` snapshots the previous `scripts/.tmp/schedule.json` as `prior-schedule.json` for continuity. Schedule Delta rendering is **not** in the current report (delta code retained in `sprintkit/delta.py` for future use).

## Five-step process → pipeline

```
PLAN → FETCH (MCP) → RUN (wrapper script) → REPORT (paste stdout)
```

| Step | What | Module |
|------|------|--------|
| 1. Load sprint items | MCP fetch → `issues.json`; derive active sprint window | `_shared/jira-fetch-sprint.md` + `sprintkit/sprint_window.py` |
| 2. Map task → platform/team | first `\|` prefix, then Jira **Teams** field | `sprintkit/teams.py` |
| 3. Map leave → team leaves | `Leave \| Planned/Unplanned` | `sprintkit/stages.py` |
| 4. Map task → stage | assessment / development / testing / release / UAT | `sprintkit/stages.py` |
| 5. Calculate team effort per stage | per epic / team / member, 6h/day | `sprintkit/timeline.py` |

Scheduling (`normalize.py` + `schedule.py`, 8h/day), bug effort (`bugs.py`), data-quality flags (`quality.py`), and rendering (`render/`) are wired by `sprintkit/pipeline.py` → `scripts/sprint_report.py`.

## Scripts

### Wrappers (post-fetch)

```bash
python scripts/run_sprint_report.py --issues scripts/.tmp/issues.json --config .cursor/config/em-config.yaml
python scripts/run_epic_estimation.py --epic VP-800 --issues scripts/.tmp/epic-VP-800-issues.json
python scripts/run_epic_estimation_slack.py --epic VP-800 --issues scripts/.tmp/epic-VP-800-issues.json
```

### Low-level CLIs

```bash
python scripts/sprint_report.py --issues scripts/.tmp/issues.json --config .cursor/config/em-config.yaml --summary
python scripts/epic_estimation.py --epic VP-800 --issues scripts/.tmp/epic-VP-800-issues.json --write-canvas --summary-only
python scripts/epic_estimation_slack.py --epic VP-800 --issues scripts/.tmp/epic-VP-800-issues.json --write-canvas
```

Sprint options: `--recalc`, `--prior-schedule`, `--standup`, `--sprint-start/--sprint-end`, `--today`, `--output`.

Epic options: `--write-canvas [PATH]`, `--summary-only`, `--dry-run`, `--check-slack` (slack CLI).

### Snapshots (`scripts/.tmp/`)

| File | Source |
|------|--------|
| `sprint-meta.json` | active sprint window |
| `engine-input.json` | `normalize.py` |
| `schedule.json` | `schedule.py` |
| `prior-schedule.json` | `--recalc` snapshot |
| `timeline-breakdown.json` | `timeline.py` |
| `bug-effort-breakdown.json` | `bugs.py` |

## Package (`scripts/sprintkit/`)

`config.py` · `cli_common.py` · `jira_model.py` · `teams.py` · `stages.py` · `sprint_window.py` · `normalize.py` · `schedule.py` · `delta.py` · `timeline.py` · `stage_dates.py` · `bugs.py` · `quality.py` · `pipeline.py` · `epic_pipeline.py` · `slack_client.py` · `render/{markdown,sections,report,epic_sections,canvas_tsx,summary,slack_blocks}.py` · `templates/epic-estimation.canvas.tsx`

Tests: `scripts/tests/` · Fixtures: `scripts/tests/fixtures/`

## `.cursor/` layout

```
.cursor/
├── WORKFLOW.md
├── agents/sprint-analyst.md
├── commands/           # thin slash-command triggers
├── config/em-config.yaml
├── rules/              # em-workflow, schedule-engine, jira-read-only
└── skills/
    ├── _shared/        # jira-fetch-sprint, jira-fetch-epic, post-run
    ├── sprint-report/
    ├── epic-estimation/
    ├── epic-estimation-send-slack/
    ├── jira-domain/    # reference
    ├── delivery-flow/  # reference
    └── improve-workflow/
```

## Config & docs

- Config: `.cursor/config/em-config.yaml` (`workflow.canvasDir` optional)
- Jira guide: `docs/JIRA-BEST-PRACTICES.md`
- Cloud env: `.cursor/environment.json` · Slack: `.env.local` or Cursor Cloud Secrets
