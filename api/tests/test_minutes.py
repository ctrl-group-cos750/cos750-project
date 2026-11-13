"""The minutes a student is shown for each module follow the content as written (ID document §4.4).

Until 13 Nov the modules showed the plan's 74 minutes while the content took about 180, so the app
told students less than half the time it takes. This estimate is the one the ID document uses:
reading at the narration scripts' 130 words a minute, plus a fixed time to answer each kind of
activity. Support segments (shown only to a student who struggles) and bonus quests (optional) are
left out. If the content changes enough to move a module's estimate by more than a third, update
its `estimated_minutes` in the fixtures, and Table 4.
"""

import json
import re
from typing import Any

import pytest

from app.seed import FIXTURES

WORDS_PER_MINUTE = 130
# Minutes to answer, beyond reading the item: a guess per kind, from the ID document's "about a
# minute per multiple-choice item" and "about three minutes per code item".
ANSWER = {
    "multiple_choice": 0.5,
    "matching": 0.75,
    "fill_in": 0.5,
    "parsons": 1.5,
    "trace": 3.0,
    "fix_the_bug": 2.0,
    "choose_tests": 1.5,
}


def _words(text: str | None) -> int:
    return len(re.findall(r"\w+", text or ""))


def _activities() -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for path in sorted(FIXTURES.glob("*.json")):
        for a in json.loads(path.read_text()).get("activities", []):
            out[a["id"]] = a
    return out


def _activity_minutes(a: dict[str, Any]) -> float:
    c = a["config"]
    minutes = ANSWER.get(a["kind"], 1.0) + _words(json.dumps(c)) / WORDS_PER_MINUTE
    if a["kind"] == "fill_in":
        minutes += 0.5 * len(c.get("blanks", []))
    if a["kind"] == "matching":
        minutes += 0.25 * len(c.get("left", []))
    return minutes


def estimate(module: dict[str, Any], activities: dict[int, dict[str, Any]]) -> float:
    total = 0.0
    for s in module["segments"]:
        if s.get("support_for") is not None:
            continue
        if s.get("activity_id") is not None:
            a = activities[s["activity_id"]]
            if a.get("purpose") != "bonus":
                total += _activity_minutes(a)
        else:
            # Text, a worked example (a minute more to study it), or a video's narration.
            extra = 1.0 if s["kind"] in ("worked_example", "video") else 0.25
            total += _words(s.get("body")) / WORDS_PER_MINUTE + extra
    return total


MODULES = [json.loads(p.read_text())["modules"][0] for p in sorted(FIXTURES.glob("module-*.json"))]


@pytest.mark.parametrize("module", MODULES, ids=lambda m: f"module {m['id']}")
def test_a_modules_minutes_follow_its_content(module: dict[str, Any]) -> None:
    content = estimate(module, _activities())
    shown = module["estimated_minutes"]
    assert content * 2 / 3 <= shown <= content * 4 / 3, (module["id"], shown, round(content))
