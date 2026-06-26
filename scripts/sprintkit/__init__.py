"""sprintkit — Engineering Manager sprint report pipeline.

Modules map to the five-step process:

1. Load sprint items        -> sprint_window.py (+ MCP fetch by the agent)
2. Map task -> platform/team -> teams.py
3. Map leave -> team leaves  -> stages.py
4. Map task -> stage         -> stages.py
5. Calculate efforts/stage   -> timeline.py

Scheduling (normalize.py + schedule.py), bug effort (bugs.py), data quality
(quality.py), and rendering (render/) build the three report sections, wired
together by pipeline.py and exposed through scripts/sprint_report.py.
"""
