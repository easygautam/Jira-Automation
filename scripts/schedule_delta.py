#!/usr/bin/env python3
"""Compare two schedule.json snapshots for recalculate / Schedule Delta report."""

from __future__ import annotations

from typing import Any


def _schedule_rows(schedule: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index all items by key; scheduled rows include dates, unscheduled do not."""
    index: dict[str, dict[str, Any]] = {}
    for row in schedule.get("scheduled") or []:
        key = row.get("key")
        if key:
            index[key] = {**row, "scheduled": True}
    for row in schedule.get("unscheduled") or []:
        key = row.get("key")
        if key and key not in index:
            index[key] = {**row, "scheduled": False, "startDate": None, "dueDate": None}
    return index


def compute_schedule_delta(
    prior: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """
    Diff prior vs current schedule snapshots.

    Returns lists: newly_scheduled, newly_unscheduled, date_changes, status_changes.
    """
    prior_idx = _schedule_rows(prior)
    curr_idx = _schedule_rows(current)
    all_keys = set(prior_idx) | set(curr_idx)

    newly_scheduled: list[dict[str, Any]] = []
    newly_unscheduled: list[dict[str, Any]] = []
    date_changes: list[dict[str, Any]] = []
    status_changes: list[dict[str, Any]] = []

    for key in sorted(all_keys):
        p = prior_idx.get(key)
        c = curr_idx.get(key)
        p_sched = bool(p and p.get("scheduled"))
        c_sched = bool(c and c.get("scheduled"))

        if not p_sched and c_sched:
            newly_scheduled.append(
                {
                    "key": key,
                    "startDate": c.get("startDate"),
                    "dueDate": c.get("dueDate"),
                    "status": c.get("status"),
                }
            )
            continue

        if p_sched and not c_sched:
            newly_unscheduled.append(
                {
                    "key": key,
                    "priorStart": p.get("startDate"),
                    "priorDue": p.get("dueDate"),
                    "reason": (c or p or {}).get("reason", "missing_estimate"),
                }
            )
            continue

        if p_sched and c_sched:
            if p.get("startDate") != c.get("startDate") or p.get("dueDate") != c.get("dueDate"):
                date_changes.append(
                    {
                        "key": key,
                        "priorStart": p.get("startDate"),
                        "priorDue": p.get("dueDate"),
                        "startDate": c.get("startDate"),
                        "dueDate": c.get("dueDate"),
                    }
                )
            if p.get("status") != c.get("status"):
                status_changes.append(
                    {
                        "key": key,
                        "priorStatus": p.get("status"),
                        "status": c.get("status"),
                    }
                )

    return {
        "newly_scheduled": newly_scheduled,
        "newly_unscheduled": newly_unscheduled,
        "date_changes": date_changes,
        "status_changes": status_changes,
    }


def delta_has_changes(delta: dict[str, list[dict[str, Any]]]) -> bool:
    return any(delta.get(k) for k in delta)


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Diff two schedule JSON files")
    parser.add_argument("--prior", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    prior = json.loads(Path(args.prior).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    result = compute_schedule_delta(prior, current)
    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out + "\n", encoding="utf-8")
    else:
        print(out)


if __name__ == "__main__":
    main()
