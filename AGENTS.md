# AGENTS.md

## Cursor Cloud specific instructions

Pure-Python EM workflow toolkit (`sprintkit`). No web server. **Canonical workflow:** `.cursor/WORKFLOW.md`.

### Environment
- Virtualenv: `.venv/` (gitignored). Activate: `. .venv/bin/activate`
- Runtime dependency: `PyYAML` (`requirements.txt`)

### Test / lint / build
- Tests: `python -m pytest scripts/tests -q`
- Syntax: `python -m compileall -q scripts`

### Running (fixtures — no live Jira)

```bash
python scripts/sprint_report.py --issues scripts/tests/fixtures/mini_issues.json \
  --config .cursor/config/em-config.yaml --project VP --output reports/sprint-demo.md --summary

python scripts/run_epic_estimation.py --epic VP-800 \
  --issues scripts/tests/fixtures/epic_cli_issues.json

python scripts/run_epic_setup.py --epic PPL-1546 \
  --issues scripts/tests/fixtures/epic_setup_empty.json
```

Live runs: agent MCP fetch → wrapper scripts (`run_sprint_report.py`, `run_epic_estimation.py`, `run_epic_estimation_slack.py`). See `.cursor/WORKFLOW.md`.

### Gotchas
- `reports/sprint-*.md` and `scripts/.tmp/` are gitignored
- Jira MCP is **read-only** by default (`.cursor/rules/jira-read-only.mdc`)
- `--recalc` snapshots `prior-schedule.json`; report has three sections (no Schedule Delta section)
