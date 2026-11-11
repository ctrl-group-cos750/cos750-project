"""A test-only support group for module 2 (FR-8.4, #172), on top of the repository's fixtures.

The real support content is a separate card (#173). Until it lands, the tests use this, and so can
a local run of the app (`PYTHONPATH=. python tests/support_fixture.py <folder>`, then load that
folder): the repository's fixtures, with a worked example and one fresh question for objective 6
put in right after module 2's base practice on it (segments 206 to 208), as the content will be
placed. Any real support content (#173) is left out first, so the tests see only this group. Ids
are 280 and 281, clear of the real support, which uses module 2's 90s.
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.seed import FIXTURES

MODULE = 2
OBJECTIVE = 6
AFTER_SEGMENT = 208  # the last of module 2's base practice on objective 6
SUPPORT_SEGMENTS = (280, 281)
SUPPORT_ACTIVITY = 281

SUPPORT: list[dict[str, Any]] = [
    {
        "id": 280,
        "kind": "worked_example",
        "title": "Another way to see it: add_edge",
        "body": (
            "Let's build one edge together, a line at a time.\n\n"
            "```python\ndef add_edge(self, u, v):\n    self.adj[u].append(v)\n"
            "    self.adj[v].append(u)  # undirected: both ways\n```\n\n"
            "Each vertex's list gets the other one, so the edge can be walked from either end."
        ),
        "support_for": OBJECTIVE,
    },
    {
        "id": 281,
        "kind": "activity",
        "title": "Try a fresh one",
        "activity_id": SUPPORT_ACTIVITY,
        "support_for": OBJECTIVE,
    },
]

ACTIVITY: dict[str, Any] = {
    "id": SUPPORT_ACTIVITY,
    "kind": "multiple_choice",
    "title": "Both ways",
    "module_id": MODULE,
    "objective_id": OBJECTIVE,
    "purpose": "practice",
    "config": {
        "prompt": "After `g.add_edge('A', 'B')` on an undirected graph, which lists hold a vertex?",
        "options": [
            {"id": "a", "label": "`adj['A']` holds `'B'` and `adj['B']` holds `'A'`"},
            {"id": "b", "label": "Only `adj['A']` holds `'B'`"},
            {"id": "c", "label": "Only `adj['B']` holds `'A'`"},
        ],
    },
    "solution": {"correct": "a"},
    "hints": [
        {"level": 1, "body": "An undirected edge can be walked either way."},
        {"level": 2, "body": "So each end needs to know about the other."},
        {"level": 3, "body": "`add_edge` appends to two lists, not one."},
        {"level": 4, "body": "Both: `adj['A']` gets `'B'` and `adj['B']` gets `'A'`."},
    ],
}


def write_base_fixtures(folder: Path) -> Path:
    """Copy the repository's fixtures into `folder` without any support segments (and the
    activities only they show): the content as staging has it, before support. Returns `folder`."""
    folder.mkdir(parents=True, exist_ok=True)
    for path in FIXTURES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        dropped: set[int] = set()
        for module in data.get("modules", []):
            support = [s for s in module["segments"] if s.get("support_for") is not None]
            dropped |= {s["activity_id"] for s in support if s.get("activity_id") is not None}
            module["segments"] = [s for s in module["segments"] if s not in support]
        if "activities" in data:
            data["activities"] = [a for a in data["activities"] if a["id"] not in dropped]
        (folder / path.name).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


def write_support_fixtures(folder: Path) -> Path:
    """The base fixtures (`write_base_fixtures`) in `folder`, with this support group added.
    Returns `folder`."""
    write_base_fixtures(folder)
    target = folder / f"module-{MODULE}.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    segments = data["modules"][0]["segments"]
    at = next(i for i, s in enumerate(segments) if s["id"] == AFTER_SEGMENT) + 1
    segments[at:at] = SUPPORT
    data["activities"].append(ACTIVITY)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return folder


if __name__ == "__main__":
    print(write_support_fixtures(Path(sys.argv[1])))
