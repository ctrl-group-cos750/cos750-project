#!/usr/bin/env python3
"""Turns the pilot's data into the tables the ID document's §8.4 asks for (#76).

    python3 scripts/pilot-analysis.py <folder with the four CSV files> > pilot-results.md

The folder holds the CSV files the staff portal's pilot data page downloads (`/staff/pilot`):
`*attempts*.csv`, `*hints*.csv`, `*events*.csv` and `*objective-results*.csv`. Only the standard
library is used, so it runs anywhere Python 3.11+ does. Students appear by internal id only.

What it reports, all from the data (nothing is estimated):

- **Time per module:** first `segment_viewed` in the module to `module_completed`, against the
  minutes the app shows (`estimated_minutes` in the fixtures). Gaps over 30 minutes between two
  events are left out, so a break isn't counted as work.
- **Items:** for each activity, how many students answered it, the share right first time, the
  mean number of attempts, and how many used hint 3 or 4 (the worked answer).
- **Mastery items (module 6):** difficulty p (the share right) and discrimination, the point-biserial
  correlation of the item with the rest of the check (Crocker and Algina). With a handful of pilot
  participants these are indications, not measurements; the write-up should say so.
- **Objectives:** how many students ended in each state.
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from itertools import pairwise
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "api" / "app" / "seed"
NONE = "-"  # an empty cell
BREAK = 30 * 60  # seconds: a longer gap between two events is a break, not work


def read(folder: Path, part: str) -> list[dict[str, str]]:
    files = sorted(folder.glob(f"*{part}*.csv"))
    if not files:
        sys.exit(f"No *{part}*.csv in {folder}")
    with files[-1].open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def content() -> tuple[dict[int, dict], dict[int, int], dict[int, dict]]:
    """Activities by id, each segment's module, and modules by id, from the fixtures."""
    activities: dict[int, dict] = {}
    segment_module: dict[int, int] = {}
    modules: dict[int, dict] = {}
    for path in sorted(SEED.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for a in data.get("activities", []):
            activities[a["id"]] = a
        for m in data.get("modules", []):
            modules[m["id"]] = m
            for s in m["segments"]:
                segment_module[s["id"]] = m["id"]
    return activities, segment_module, modules


def point_biserial(item: list[int], rest: list[float]) -> float | None:
    if len(set(item)) < 2 or len(set(rest)) < 2:
        return None
    right = [r for i, r in zip(item, rest, strict=True) if i]
    wrong = [r for i, r in zip(item, rest, strict=True) if not i]
    p = len(right) / len(item)
    sd = statistics.pstdev(rest)
    return (statistics.mean(right) - statistics.mean(wrong)) / sd * (p * (1 - p)) ** 0.5


def module_times(
    events: list[dict[str, str]], segment_module: dict[int, int]
) -> dict[int, list[float]]:
    """Minutes each student spent on each module they completed."""
    by_student: dict[str, list[tuple[datetime, str, str]]] = defaultdict(list)
    for e in events:
        by_student[e["user_id"]].append((when(e["created_at"]), e["type"], e["ref"]))
    minutes: dict[int, list[float]] = defaultdict(list)
    for timeline in by_student.values():
        timeline.sort()
        start: dict[int, int] = {}  # module -> index of its first event
        for i, (_, kind, ref) in enumerate(timeline):
            if kind == "segment_viewed" and ref.startswith("segment:"):
                module = segment_module.get(int(ref.split(":")[1]))
                if module is not None:
                    start.setdefault(module, i)
            if kind == "module_completed" and ref.startswith("module:"):
                module = int(ref.split(":")[1])
                if module in start:
                    span = timeline[start[module] : i + 1]
                    seconds = sum(
                        gap
                        for a, b in pairwise(span)
                        if (gap := (b[0] - a[0]).total_seconds()) <= BREAK
                    )
                    minutes[module].append(seconds / 60)
    return minutes


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    attempts = read(folder, "attempts")
    hints = read(folder, "hints")
    events = read(folder, "events")
    results = read(folder, "objective-results")
    activities, segment_module, modules = content()
    students = {r["user_id"] for r in attempts} | {e["user_id"] for e in events}

    print("# Pilot results\n")
    print(
        f"{len(students)} participants; {len(attempts)} answers, {len(hints)} hints shown, "
        f"{len(events)} events.\n"
    )

    print("## Time per module\n")
    print(
        "| Module | Shown to students (min) | Students who finished it | Median (min) | Range (min) |"
    )
    print("|---|---|---|---|---|")
    times = module_times(events, segment_module)
    for mid, m in sorted(modules.items()):
        t = times.get(mid, [])
        median = f"{statistics.median(t):.0f}" if t else NONE
        spread = f"{min(t):.0f} to {max(t):.0f}" if t else NONE
        print(
            f"| {mid}. {m['title']} | {m['estimated_minutes']} | {len(t)} | {median} | {spread} |"
        )

    print("\n## Items\n")
    by_item: dict[int, dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    for a in attempts:
        by_item[int(a["activity_id"])][a["user_id"]].append(a)
    print("| Id | Item | Kind | Students | Right first time | Mean attempts | Used hint 3 or 4 |")
    print("|---|---|---|---|---|---|---|")
    for aid in sorted(by_item):
        per_student = by_item[aid]
        firsts = [sorted(v, key=lambda r: r["created_at"])[0] for v in per_student.values()]
        right = sum(r["correct"] in ("True", "true", "1") for r in firsts)
        helped = sum(any(int(r["hint_level"] or 0) >= 3 for r in v) for v in per_student.values())
        mean = statistics.mean(len(v) for v in per_student.values())
        title = activities.get(aid, {}).get("title", firsts[0]["activity_title"])
        kind = firsts[0]["activity_kind"]
        n = len(per_student)
        print(f"| {aid} | {title} | {kind} | {n} | {right}/{n} | {mean:.1f} | {helped}/{n} |")

    print("\n## Mastery items (module 6)\n")
    mastery = sorted(
        i
        for i, a in activities.items()
        if a.get("purpose") == "mastery" and a.get("module_id") == 6
    )
    answered = [s for s in students if all(s in by_item.get(i, {}) for i in mastery)]
    if len(answered) < 3:
        print(
            f"Only {len(answered)} participants answered every mastery item: too few for item statistics.\n"
        )
    else:
        scores = {
            s: {
                i: int(
                    sorted(by_item[i][s], key=lambda r: r["created_at"])[0]["correct"]
                    in ("True", "true", "1")
                )
                for i in mastery
            }
            for s in answered
        }
        print(
            f"{len(answered)} participants answered every mastery item. Discrimination is the "
            "point-biserial correlation with the rest of the check; with this few participants "
            "read it as an indication only.\n"
        )
        print("| Id | Objective | Difficulty p | Discrimination |")
        print("|---|---|---|---|")
        for i in mastery:
            item = [scores[s][i] for s in answered]
            rest = [sum(v for k, v in scores[s].items() if k != i) for s in answered]
            r = point_biserial(item, rest)
            p = sum(item) / len(item)
            print(
                f"| {i} | {activities[i].get('objective_id')} | {p:.2f} | {NONE if r is None else f'{r:.2f}'} |"
            )

    print("\n## Objectives\n")
    states = ["met_independently", "met_with_support", "not_yet", "not_attempted"]
    tally: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(states, 0))
    for r in results:
        tally[r["objective_id"]][r["state"]] = tally[r["objective_id"]].get(r["state"], 0) + 1
    print("| Objective | Met on their own | Met with support | Not yet | Not attempted |")
    print("|---|---|---|---|---|")
    for o in sorted(tally, key=int):
        t = tally[o]
        print(
            f"| {o} | {t['met_independently']} | {t['met_with_support']} | {t['not_yet']} | {t['not_attempted']} |"
        )


if __name__ == "__main__":
    main()
