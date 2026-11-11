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
from app.services.mastery import Rule

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


# The segment that gains attention in each module (Gagné's event 1): the module's first text or
# worked-example segment, which opens with a question. Modules 2 and 4 start with a video that
# may not be recorded yet, so their hook opens the worked example after it; module 3's hook is
# its first video (the campus puzzle). Module 5 has no segments yet (#86). No segment is added
# for a hook: saved progress is a segment index, so a new segment would move every student.
HOOKS = {0: 1, 1: 101, 2: 204, 3: 313, 4: 404, 6: 601}


def test_every_module_with_content_opens_by_gaining_attention() -> None:
    for m in CONTENT.modules:
        if not m.segments:
            assert m.id == 5
            continue
        if m.id == 3:
            assert m.segments[0].id == HOOKS[3]
            assert m.segments[0].kind == "video"
            continue
        first = next(s for s in m.segments if s.kind in ("text", "worked_example"))
        assert first.id == HOOKS[m.id], m.id
        # It opens with a question, or puts a puzzle straight after it (module 1).
        after = m.segments[m.segments.index(first) + 1]
        opening = (first.body or "").split("\n\n")[0]
        assert "?" in opening or after.kind == "activity", m.id


# --- No simple strategy passes an objective -----------------------------------------------------


def first_word(label: str) -> str:
    return re.split(r"[\s.,:;]", label.strip(), maxsplit=1)[0].lower()


def odd_one_out(a: ActivityFixture) -> str | None:
    """The option whose first word no other option starts with ("the only No"), if there is one."""
    words = Counter(first_word(o["label"]) for o in a.config["options"])
    odd = [o["id"] for o in a.config["options"] if words[first_word(o["label"])] == 1]
    return odd[0] if len(odd) == 1 else None


def longest(a: ActivityFixture) -> str:
    return str(max(a.config["options"], key=lambda o: len(o["label"]))["id"])


def most_like_the_rest(a: ActivityFixture) -> str | None:
    """The option closest to all the others, in order as well as words: the "middle" one that each
    distractor changes in one way (vertices swapped, or the direction flipped). None on a tie."""
    opts = a.config["options"]
    score = {
        o["id"]: sum(
            difflib.SequenceMatcher(None, o["label"].lower(), p["label"].lower()).ratio()
            for p in opts
            if p is not o
        )
        for o in opts
    }
    best = max(score.values())
    top = [i for i, v in score.items() if v > best - 0.02]
    return top[0] if len(top) == 1 else None


def nearest_to_the_others(a: ActivityFixture) -> str | None:
    """Split each option into its parts ("Vertices: … . Edges: … . Directed.") and pick the one
    that differs from the others in the fewest parts in total, if only one does: the "middle"
    option each distractor changes in one way. Staging's objective 3 items fell to it, 4 of 4."""
    split = {o["id"]: re.split(r"(?<=\.)\s+", o["label"].strip()) for o in a.config["options"]}
    if len({len(p) for p in split.values()}) != 1 or len(next(iter(split.values()))) < 2:
        return None

    def apart(x: list[str], y: list[str]) -> int:
        return sum(i != j for i, j in zip(x, y, strict=True))

    total = {i: sum(apart(p, q) for j, q in split.items() if j != i) for i, p in split.items()}
    best = min(total.values())
    hits = [i for i, t in total.items() if t == best]
    return hits[0] if len(hits) == 1 else None


def at(index: int) -> Any:
    def pick(a: ActivityFixture) -> str | None:
        opts = a.config["options"]
        return str(opts[index]["id"]) if index < len(opts) else None

    return pick


def middle(a: ActivityFixture) -> str:
    opts = a.config["options"]
    return str(opts[len(opts) // 2]["id"])


STRATEGIES = {
    "odd one out by first word": odd_one_out,
    "longest option": longest,
    "most like the rest": most_like_the_rest,
    "nearest to the other options": nearest_to_the_others,
    "always the first option": at(0),
    "always the second option": at(1),
    "always the middle option": middle,
    "always option a": lambda a: "a",
    "always option b": lambda a: "b",
}
OBJECTIVES = {o.id: o for o in CONTENT.objectives}
CHECK_SETS = {
    "module 6": [
        ACTIVITIES[s.activity_id]
        for m in CONTENT.modules
        if m.id == 6
        for s in m.segments
        if s.activity_id is not None
    ],
    "review path": [
        ACTIVITIES[s.activity_id]
        for r in CONTENT.review_paths
        for s in r.segments
        if s.activity_id is not None and ACTIVITIES[s.activity_id].purpose == "mastery"
    ],
}


def parts(a: ActivityFixture) -> int:
    """Only multiple choice is one part; a strategy that picks an option can't answer the rest,
    so they count as wrong (generous to the strategy only where it can play at all)."""
    match a.kind:
        case "matching":
            return len(a.config["left"])
        case "fill_in":
            return len(a.config["blanks"])
        case "parsons" | "fix_the_bug":
            return len(a.solution["order"])
        case "choose_tests":
            return len(a.config["tests"])
    return 1


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("where", CHECK_SETS)
def test_no_simple_strategy_meets_any_objective(where: str, strategy: str) -> None:
    """Answering every multiple-choice item by a surface rule must not meet an objective's rule
    (#147: "pick the only Yes/No" met objective 4, "the middle option" objective 3)."""
    pick = STRATEGIES[strategy]
    for objective, o in OBJECTIVES.items():
        items = [a for a in CHECK_SETS[where] if a.objective_id == objective]
        mc = [a for a in items if a.kind == "multiple_choice"]
        if not mc:
            continue
        right = sum(pick(a) == a.solution["correct"] for a in mc)
        total = sum(parts(a) for a in items)
        rule = Rule(pass_fraction=o.pass_fraction, max_wrong=o.max_wrong)
        assert not rule.met(right, total), (where, strategy, objective, right, total)


# Option ids whose text changed meaning in #147. They are retired, never reused: an old attempt's
# `selected` must not be read as the new text (the lesson of #117 and #133).
RETIRED = {614: "b", 615: "c", 616: "c", 617: "b", 1402: "c", 1403: "c", 1404: "b", 1405: "c"}


def test_a_retired_option_id_is_never_reused() -> None:
    for activity_id, option_id in RETIRED.items():
        options = {o["id"] for o in ACTIVITIES[activity_id].config["options"]}
        assert option_id not in options, activity_id
