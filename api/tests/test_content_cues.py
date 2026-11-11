"""Content quality across every fixture (#147): questions a student can only answer by knowing
the material, in words the app can show.

These are the checks an item writer would make by eye, run on every activity so new content keeps
to them (ID document §7.3 to 7.4, SE document FR-4.3):

- no answer cue: the right option is spread over the positions and is rarely the clearly longest
  one, and no matching item's answers run straight down the diagonal;
- plain-text fields (prompts, options, hints, feedback) carry no Markdown, because the app shows
  them as text: backticks and code fences would appear literally and a code block's line breaks
  would collapse (segment bodies are Markdown and may hold code);
- "found" and "visited" mean what module 3 says: found when a vertex joins the queue, visited when
  it leaves; the code's `visited` set holds the found vertices (module 4);
- a mastery item is not a copy of a practice item;
- nothing a student sees is placeholder text, and nothing promises behaviour the app doesn't have;
- every module with content starts by gaining attention (Gagné's event 1, ID document Table 3).
"""

import difflib
import re
from collections import Counter
from collections.abc import Iterator
from typing import Any

import pytest

from app.seed import ActivityFixture, FixtureFile, read_fixtures

CONTENT: FixtureFile = read_fixtures()
ACTIVITIES = {a.id: a for a in CONTENT.activities}
MULTIPLE_CHOICE = [a for a in CONTENT.activities if a.kind == "multiple_choice"]
MATCHING = [a for a in CONTENT.activities if a.kind == "matching"]
SEGMENTS = [s for m in CONTENT.modules for s in m.segments] + [
    s for r in CONTENT.review_paths for s in r.segments
]

# Fields that hold code a student reads as code (a monospaced block or a code line), not text.
CODE_FIELDS = {"code", "text"}
MARKDOWN = re.compile(r"`|\*\*|^#|\[[^\]]*\]\(|^\s*[-*] ", re.M)


def plain_text(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every string a student is shown as plain text, with where it is."""
    if isinstance(value, str):
        if path.rsplit(".", 1)[-1] not in CODE_FIELDS:
            yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from plain_text(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from plain_text(item, f"{path}[{index}]")


def shown_text(a: ActivityFixture) -> Iterator[tuple[str, str]]:
    yield from plain_text(a.config, "config")
    yield from plain_text(a.solution.get("feedback", {}), "feedback")
    for h in a.hints:
        yield f"hint {h.level}", h.body


def right_index(a: ActivityFixture) -> int:
    return [o["id"] for o in a.config["options"]].index(a.solution["correct"])


# --- Answer cues ------------------------------------------------------------------------------


def test_the_right_option_is_spread_over_the_positions() -> None:
    places = Counter(right_index(a) for a in MULTIPLE_CHOICE)
    # Three options each, mostly: about a third each. Staging had 29 of 50 first.
    assert max(places.values()) <= 0.4 * len(MULTIPLE_CHOICE), places
    assert {0, 1, 2} <= set(places)


@pytest.mark.parametrize("purpose", ["diagnostic", "retrieval", "practice", "review"])
def test_no_kind_of_question_always_puts_the_right_option_first(purpose: str) -> None:
    items = [a for a in MULTIPLE_CHOICE if a.purpose == purpose]
    assert items
    assert sum(right_index(a) == 0 for a in items) <= max(1, len(items) // 2), purpose


def test_the_right_option_is_rarely_the_clearly_longest() -> None:
    def clearly_longest(a: ActivityFixture) -> bool:
        lengths = {o["id"]: len(o["label"]) for o in a.config["options"]}
        right = lengths.pop(a.solution["correct"])
        return right > 1.2 * max(lengths.values())

    longest = [a.id for a in MULTIPLE_CHOICE if clearly_longest(a)]
    # A few are unavoidable: an undirected graph's dictionary lists every edge twice (203).
    assert len(longest) <= 0.1 * len(MULTIPLE_CHOICE), longest


@pytest.mark.parametrize("a", MATCHING, ids=lambda a: str(a.id))
def test_no_matching_answers_run_down_the_diagonal(a: ActivityFixture) -> None:
    right = [r["id"] for r in a.config["right"]]
    if len(right) <= 2:
        return  # directed or undirected: two choices, no diagonal to speak of
    places = [right.index(a.solution["pairs"][item["id"]]) for item in a.config["left"]]
    assert places != list(range(len(places)))


@pytest.mark.parametrize(
    "a", [a for a in MATCHING if len(a.config["left"]) <= 3], ids=lambda a: str(a.id)
)
def test_a_short_matching_item_cannot_be_finished_by_elimination(a: ActivityFixture) -> None:
    """With three pairs or fewer, a forced last pair is a third of the answer or more (313 on
    staging): so there are more right options than left items, or one is used twice."""
    used = Counter(a.solution["pairs"].values())
    assert len(a.config["right"]) > len(a.config["left"]) or max(used.values()) > 1


# --- Plain text -------------------------------------------------------------------------------


@pytest.mark.parametrize("a", CONTENT.activities, ids=lambda a: str(a.id))
def test_plain_text_fields_carry_no_markdown(a: ActivityFixture) -> None:
    for where, text in shown_text(a):
        assert not MARKDOWN.search(text), f"{where}: {text!r}"
        assert "\n" not in text, f"{where}: a line break collapses in plain text"


# --- Found and visited (module 3, module 4) ----------------------------------------------------

WRONG_WORDS = [
    "unvisited",  # a vertex waiting in the queue is unvisited, yet must not be added again
    "marked visited",
    "marked as visited",
    "mark it visited",
    "mark each neighbour visited",
    "is visited when it joins",  # the code's visited set takes it then; the vertex is only found
    "is visited as it joins",
]


def everything_shown() -> Iterator[tuple[str, str]]:
    for a in CONTENT.activities:
        for where, text in shown_text(a):
            yield f"activity {a.id} {where}", text
    for s in SEGMENTS:
        if s.body:
            yield f"segment {s.id}", s.body


def test_found_and_visited_mean_what_module_3_says() -> None:
    for where, text in everything_shown():
        for words in WRONG_WORDS:
            assert words not in text.lower(), f"{where}: {text!r}"


# --- Mastery items are not practice items -----------------------------------------------------

# Module 6's items. A review path's fresh items (1602 is the practice program again) are #148's.
MASTERY = [a for a in CONTENT.activities if a.purpose == "mastery" and a.module_id == 6]
PRACTICE = [a for a in CONTENT.activities if a.purpose == "practice"]


def filled(a: ActivityFixture) -> list[str]:
    """The finished program, without its comments and blank lines."""
    answers = {str(k): v for k, v in a.solution["answers"].items()}
    code = re.sub(r"__(\d+)__", lambda m: answers[m.group(1)], a.config["code"])
    lines = (line.split("#")[0].rstrip() for line in code.splitlines())
    return [line for line in lines if line.strip()]


@pytest.mark.parametrize("a", [a for a in MASTERY if a.kind == "parsons"], ids=lambda a: str(a.id))
def test_a_mastery_parsons_item_is_not_the_practice_one(a: ActivityFixture) -> None:
    mine = {line["text"].strip() for line in a.config["lines"]}
    for p in (p for p in PRACTICE if p.kind == "parsons"):
        theirs = {line["text"].strip() for line in p.config["lines"]}
        assert len(mine & theirs) <= len(theirs) // 2, p.id


@pytest.mark.parametrize("a", [a for a in MASTERY if a.kind == "fill_in"], ids=lambda a: str(a.id))
def test_a_mastery_fill_in_is_not_a_practice_one(a: ActivityFixture) -> None:
    for p in (p for p in PRACTICE if p.kind == "fill_in"):
        assert filled(a) != filled(p), p.id  # 620 was 406 with fewer blanks (#147)


def test_a_mastery_question_does_not_restate_a_practice_situation() -> None:
    def sentences(a: ActivityFixture) -> list[str]:
        texts = [str(a.config.get("prompt", ""))] + [x["label"] for x in a.config.get("left", [])]
        return [s for t in texts for s in re.split(r"(?<=[.?])\s", t) if len(s) > 30]

    practice = [s for p in PRACTICE for s in sentences(p)]
    for a in (a for a in MASTERY if a.kind == "multiple_choice"):
        for mine in sentences(a):
            for theirs in practice:
                ratio = difflib.SequenceMatcher(None, mine.lower(), theirs.lower()).ratio()
                assert ratio < 0.6, (a.id, mine, theirs)


# --- What the student sees --------------------------------------------------------------------


def test_no_graph_scenario_is_a_placeholder() -> None:
    for g in CONTENT.graphs:
        assert "placeholder" not in g.name.lower(), g.name


def test_module_0_promises_no_skip_the_app_does_not_make() -> None:
    """The diagnostic does not choose the refreshers yet (FR-8.1, #31): every one is shown."""
    module = next(m for m in CONTENT.modules if m.id == 0)
    for s in module.segments:
        assert "skip" not in (s.body or "").lower(), s.id


# The segment that gains attention in each module (Gagné's event 1). Module 3's is its first
# video; module 5 has no segments yet (#86), so it gets its opening with its content.
HOOKS = {0: 1, 1: 101, 2: 210, 3: 313, 4: 409, 6: 601}


def test_every_module_with_content_opens_by_gaining_attention() -> None:
    for m in CONTENT.modules:
        if not m.segments:
            assert m.id == 5
            continue
        first = m.segments[0]
        assert first.id == HOOKS[m.id], m.id
        assert first.kind in ("text", "video"), m.id
        if first.kind == "text":
            # It opens with a question, or puts a puzzle straight after it (module 1).
            puzzle = len(m.segments) > 1 and m.segments[1].kind == "activity"
            assert (first.body and "?" in first.body) or puzzle, m.id
