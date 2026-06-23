# EM workflow manifest

Canonical inventory for agents. **Runbook:** `.cursor/skills/sprint-report/SKILL.md`. **Agent:** `.cursor/agents/sprint-analyst.md`.

One agent (`sprint-analyst`) and one command (`/sprint-report`) drive everything. The agent fetches Jira issues; a single pipeline (`scripts/sprint_report.py` → `scripts/sprintkit/`) maps and calculates everything and renders the report.

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

## Single command

**Prerequisites:** `pip install -r requirements.txt` is recommended so `em-config.yaml` loads fully (Jira `cloudId`, custom fields). Without PyYAML the pipeline uses built-in defaults from `sprintkit/config.py` — team bucketing (Backend/QA/Web/Mobile) still works; a warning appears in the report Executive summary.

```bash
python scripts/sprint_report.py \
  --issues scripts/.tmp/issues.json \
  --config .cursor/config/em-config.yaml \
  --project {projectKey}
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

## Package (`scripts/sprintkit/`)

`config.py` · `jira_model.py` · `teams.py` · `stages.py` · `sprint_window.py` · `normalize.py` · `schedule.py` · `delta.py` · `timeline.py` · `bugs.py` · `quality.py` · `pipeline.py` · `render/{markdown,sections,report}.py`. Tests in `scripts/tests/` (incl. `test_pipeline_golden.py`); fixtures in `scripts/tests/fixtures/`.

Team prefixes: `sprintkit/teams.py` + `em-config.yaml` `teamPrefixMapping` (first `|` segment only; else **Other**). **Teams plan Other** = segment mapping failed only (`member_side_for_classification` in `timeline.py`). Stage/leave mapping: `sprintkit/stages.py` — **pipe-segment only** (no keyword substring rules); per-platform **Tech Solutioning** + **QA Test Planning** rows; `{Web|App} | UAT | …` → Product + Design team; QA requires platform in segment 2. Side labels: `resolve_side_display_map()` in `config.py`. Details: `jira-domain` skill.

**Sprint window rule:** reports cover the complete active sprint (sprint start → end) across all statuses (closed/deferred included); each section applies its own status condition. Calendar Start/End columns are deferred (no Start/End columns in member/stage tables).

## Config & entrypoints

- Jira title/estimate guide: [`docs/JIRA-BEST-PRACTICES.md`](../docs/JIRA-BEST-PRACTICES.md)
- Config: `.cursor/config/em-config.yaml`
- Commands: `sprint-report` (recalculate + standup are options), `improve-workflow` → matching skill under `.cursor/skills/`
- Rules: `em-workflow.mdc`, `schedule-engine.mdc`, `jira-read-only.mdc`
- Agent: `.cursor/agents/sprint-analyst.md`
- Skills: `sprint-report` (runbook), `jira-domain`, `delivery-flow`, `improve-workflow`

## Six deliverables (report order)

Executive summary → **Delivery items (Epics)** → **Teams plan** → **Member breakdown** → **Execution stages** → **Bug fix effort** (epic × Backend/Web/Mobile/QA/Other/Total + member detail) → **Team tasks plan** → Data quality flags → Recommended actions (→ Schedule Delta on `--recalc`).
