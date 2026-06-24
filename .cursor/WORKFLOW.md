# EM workflow manifest

Canonical inventory for agents. **Runbooks:** `.cursor/skills/sprint-report/SKILL.md` · `.cursor/skills/epic-estimation/SKILL.md`. **Agent:** `.cursor/agents/sprint-analyst.md`.

One agent (`sprint-analyst`) drives three commands. **Sprint report** fetches the active sprint and saves `reports/sprint-{date}.md`. **Epic estimation** fetches one Epic (no sprint filter), computes stage Start/End dates, and displays a **Cursor Canvas** beside chat — **never** writes under `reports/`. **Epic estimation → Slack** extends epic estimation with a Block Kit post to `#gautam-personal-agent`.

## Five-step process → pipeline

```
PLAN → FETCH (Load) → RUN (map + calculate + render) → REPORT
```

| Step | What | Module |
|------|------|--------|
| 1. Load sprint items | MCP fetch → `issues.json`; derive active sprint window | agent fetch + `sprintkit/sprint_window.py` |
| 2. Map task → platform/team | first `|` prefix, labels, components | `sprintkit/teams.py` |
| 3. Map leave → team leaves | `Leave | Planned/Unplanned` → leave buckets | `sprintkit/stages.py` |
| 4. Map task → stage | assessment / development / testing / release / UAT | `sprintkit/stages.py` |
| 5. Calculate team effort per stage | per epic / team / member, 6h/day | `sprintkit/timeline.py` |

Scheduling (`normalize.py` + `schedule.py`, 8h/day), bug effort (`bugs.py`), data-quality flags (`quality.py`), and rendering (`render/`) are wired together by `sprintkit/pipeline.py` and exposed through `scripts/sprint_report.py`.

## Single command — sprint report

**Prerequisites:** `pip install -r requirements.txt` is recommended so `em-config.yaml` loads fully (Jira `cloudId`, custom fields). Without PyYAML the pipeline uses built-in defaults from `sprintkit/config.py` — team bucketing (Backend/QA/Web/Mobile) still works; a warning appears in the report Executive summary.

```bash
python scripts/sprint_report.py \
  --issues scripts/.tmp/issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}   # optional when jira.projectKey is set in config
```

Options: `--recalc` (snapshot prior `schedule.json`, add a **Schedule Delta**), `--prior-schedule PATH`, `--standup` (chat-only summary), `--sprint-start/--sprint-end` (window override), `--today YYYY-MM-DD`, `--output PATH`.

Writes `reports/sprint-{date}.md`, prints a JSON summary (status counts, scheduled/unscheduled, sprint window), and snapshots pipeline JSON under `scripts/.tmp/`:

| Snapshot | Source |
|----------|--------|
| `sprint-meta.json` | active sprint window |
| `engine-input.json` | `normalize.py` |
| `schedule.json` | `schedule.py` (8h) |
| `timeline-breakdown.json` | `timeline.py` (6h, Task/Sub-task) |
| `bug-effort-breakdown.json` | `bugs.py` (worklog) |
| `prior-schedule.json` | `--recalc` snapshot of the previous `schedule.json` |

## Epic estimation command

No sprint window. Requires `--epic {epicKey}`. **Stdout JSON only** — agent embeds `canvas` in a `.canvas.tsx` file beside chat. No `--output`, no `reports/` file.

```bash
python scripts/epic_estimation.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

| Module | Role |
|--------|------|
| `sprintkit/epic_pipeline.py` | filter epic → timeline → stage dates → display payload |
| `sprintkit/stage_dates.py` | per-platform stage Start/End from Jira Start + calc days |
| `sprintkit/render/epic_sections.py` | markdown + canvas JSON builder |

Fetch: two-pass JQL (`epicEstimation.epicScopeJql` + `taskScopeJql` in config). Stage date rules: `delivery-flow` skill.

## Epic estimation → Slack command

Same fetch and pipeline as epic estimation, then posts Block Kit to Slack.

**Secrets:** local `.env.local` (see `.env.example`) or Cursor Cloud Agents → Secrets (`SLACK_BOT_TOKEN` as Runtime Secret). Optional `SLACK_CHANNEL_ID` avoids channel lookup on cloud.

```bash
python scripts/epic_estimation_slack.py \
  --epic {epicKey} \
  --issues scripts/.tmp/epic-{epicKey}-issues.json \
  --config .cursor/config/em-config.yaml
```

Options: `--dry-run` (Block Kit JSON only), `--check-slack` (verify token + channel, no post). Cloud install: [`.cursor/environment.json`](.cursor/environment.json).

| Module | Role |
|--------|------|
| `sprintkit/render/slack_blocks.py` | canvas JSON → Block Kit (table + monospace fallback) |
| `sprintkit/slack_client.py` | channel resolve + `chat.postMessage` |

## Package (`scripts/sprintkit/`)

`config.py` · `jira_model.py` · `teams.py` · `stages.py` · `sprint_window.py` · `normalize.py` · `schedule.py` · `delta.py` · `timeline.py` · `stage_dates.py` · `bugs.py` · `quality.py` · `pipeline.py` · `epic_pipeline.py` · `slack_client.py` · `render/{markdown,sections,report,epic_sections,slack_blocks}.py`. Tests in `scripts/tests/` (incl. `test_pipeline_golden.py`, `test_stage_dates.py`, `test_epic_pipeline.py`, `test_slack_blocks.py`); fixtures in `scripts/tests/fixtures/`.

Team prefixes: `sprintkit/teams.py` + `em-config.yaml` `teamPrefixMapping` (first `|` segment only; else **Other**). **Teams plan Other** = segment mapping failed only (`member_side_for_classification` in `timeline.py`). Stage/leave mapping: `sprintkit/stages.py` — **pipe-segment only** (no keyword substring rules); per-platform **Tech Solutioning** + **QA Test Planning** rows; `{Web|App} | UAT | …` → Product + Design team; QA requires platform in segment 2. Side labels: `resolve_side_display_map()` in `config.py`. Details: `jira-domain` skill.

**Sprint window rule:** reports cover the complete active sprint (sprint start → end) across all statuses (closed/deferred included); each section applies its own status condition. Calendar Start/End columns are deferred (no Start/End columns in member/stage tables).

## Config & entrypoints

- Jira title/estimate guide: [`docs/JIRA-BEST-PRACTICES.md`](../docs/JIRA-BEST-PRACTICES.md)
- Config: `.cursor/config/em-config.yaml`
- Commands: `sprint-report` (recalculate + standup are options), `epic-estimation` (canvas only), `epic-estimation-send-slack` (canvas + Slack), `improve-workflow` → matching skill under `.cursor/skills/`
- Rules: `em-workflow.mdc`, `schedule-engine.mdc`, `jira-read-only.mdc`
- Agent: `.cursor/agents/sprint-analyst.md`
- Skills: `sprint-report` (runbook), `epic-estimation`, `epic-estimation-send-slack`, `jira-domain`, `delivery-flow`, `improve-workflow`

## Six deliverables (report order)

Executive summary → **Delivery items (Epics)** → **Teams plan** → **Member breakdown** → **Execution stages** → **Bug fix effort** (epic × Backend/Web/Mobile/QA/Other/Total + member detail) → **Team tasks plan** → Data quality flags → Recommended actions (→ Schedule Delta on `--recalc`).
