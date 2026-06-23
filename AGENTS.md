# AGENTS.md

## Cursor Cloud specific instructions

This repo is a pure-Python EM workflow toolkit (`sprintkit`) — there is **no web server or
long-running service**. The "applications" are two CLIs in `scripts/` that read Jira issues
JSON + `.cursor/config/em-config.yaml` and produce a markdown report / JSON payload.

### Environment
- A virtualenv lives at `.venv/` (gitignored). Activate with `. .venv/bin/activate` before
  running anything. The startup/update script recreates it and installs deps, so you normally
  don't need to install anything yourself.
- Runtime dependency is just `PyYAML` (in `requirements.txt`); `pytest` is installed for the
  test suite but is **not** required (tests are stdlib `unittest`).

### Test / lint / build
- Tests: `python -m pytest scripts/tests -q` (or, without pytest: `python -m unittest discover -s scripts/tests`). All tests self-bootstrap `sys.path` to find `scripts/sprintkit`.
- No linter/formatter is configured in the repo. For a quick syntax check use
  `python -m compileall -q scripts`.
- No build step (no packaging).

### Running the apps (core functionality)
Run from the repo root. Fixtures under `scripts/tests/fixtures/` and `scripts/fixtures/` are
handy stand-ins for live Jira fetches.

- Sprint report (writes `reports/sprint-{date}.md` unless `--output` given):
  ```
  python scripts/sprint_report.py --issues scripts/tests/fixtures/mini_issues.json \
    --config .cursor/config/em-config.yaml --project VP --output reports/sprint-demo.md
  ```
  Add `--standup` for a chat-only summary; `--recalc` for a Schedule Delta.
- Epic estimation (stdout JSON only, no file written):
  ```
  python scripts/epic_estimation.py --epic VP-800 \
    --issues scripts/tests/fixtures/epic_cli_issues.json \
    --config .cursor/config/em-config.yaml --project VP
  ```
  Note: `--epic` must match a key actually present in the `--issues` payload, otherwise it
  exits with "No issues found for epic ...".

### Gotchas
- `reports/sprint-*.md` and `scripts/.tmp/` are gitignored; generated demo output won't show
  in `git status`.
- Live Jira fetches go through the Atlassian MCP and are **read-only by default**
  (see `.cursor/rules/jira-read-only.mdc`). For local dev/testing use the JSON fixtures.
