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
  it leaves; the code's set of found vertices is called `found`, never `visited` (module 4);
- a mastery item is not a copy of a practice item;
- nothing a student sees is placeholder text, and nothing promises behaviour the app doesn't have;
- every module with content starts by gaining attention (Gagné's event 1, ID document Table 3).
"""

import difflib
import json
import random
import re
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from app.schemas.graphs import GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, read_fixtures
from app.services.bfs import run_bfs
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
    "is visited when it joins",  # the code's found set takes it then; the vertex is only found
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


# The code's set of found vertices named `visited`: a set, a membership test or an add.
CODE_VISITED = re.compile(r"\bvisited\s*=|\bvisited\.(?:add|__)|\bin visited\b")


def everything(o: Any) -> Iterator[str]:
    if isinstance(o, dict):
        for v in o.values():
            yield from everything(v)
    elif isinstance(o, list):
        for v in o:
            yield from everything(v)
    elif isinstance(o, str):
        yield o


def test_the_code_calls_the_found_set_found() -> None:
    """In modules 4 to 6 the code's set held the vertices found (marked as they join the queue) but
    was called `visited`, while the trace table and the visualiser use "visited" for "has left the
    queue". The picture and the code disagreed on the one variable that matters (Sorva 2013; review
    13 Nov, High 3). The set is `found` everywhere, so "visited" means one thing."""
    for a in CONTENT.activities:
        for text in everything([a.config, a.solution, [h.body for h in a.hints]]):
            assert not CODE_VISITED.search(text), f"activity {a.id}: {text[:120]!r}"
    for seg in SEGMENTS:
        assert not CODE_VISITED.search(seg.body or ""), f"segment {seg.id}"


# --- Mastery items are not practice items -----------------------------------------------------

# Module 6's items. A review path's fresh items (1602 is the practice program again) are #148's.
MASTERY = [a for a in CONTENT.activities if a.purpose == "mastery" and a.module_id == 6]
# Everything on a review path: its practice and its fresh items.
REVIEWS = [a for a in CONTENT.activities if a.module_id is None]
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


@pytest.mark.parametrize(
    "a", [a for a in MASTERY if a.kind == "fix_the_bug"], ids=lambda a: str(a.id)
)
def test_a_mastery_fix_the_bug_item_is_not_a_practice_one(a: ActivityFixture) -> None:
    """621 was 504 line for line, after a worked example that prints the fix (#214 C2)."""
    mine = [line["text"] for line in a.config["lines"]]
    for p in (p for p in PRACTICE if p.kind == "fix_the_bug"):
        assert mine != [line["text"] for line in p.config["lines"]], p.id


ASSESSED_FIXES = [
    a for a in CONTENT.activities if a.kind == "fix_the_bug" and a.purpose == "mastery"
]


@pytest.mark.parametrize("a", ASSESSED_FIXES, ids=lambda a: str(a.id))
def test_an_assessed_fix_offers_a_correction_for_a_line_that_is_not_faulty(
    a: ActivityFixture,
) -> None:
    """Locating the bug is the Analyse part of objective 7. When every correction rewrites the
    faulty line (all `for n in sorted…`, all `v = queue…`), the choices point at it and only
    Understand is left (Thompson 2008; review 13 Nov, High 10). So at least one correction looks
    like a fix for a line that is not faulty."""
    fixed = {i for x in a.solution["order"] for i in (x if isinstance(x, list) else [x])}
    lines = {x["id"]: x["text"] for x in a.config["lines"]}
    faulty = [lines[i] for i in lines if i not in fixed]

    def head(text: str) -> str:
        return re.split(r"[ (.=:]", text.strip())[0]

    elsewhere = [
        c["text"]
        for c in a.config["corrections"]
        if c["id"] not in fixed and all(head(c["text"]) != head(f) for f in faulty)
    ]
    assert elsewhere, f"every wrong correction rewrites the faulty line: {faulty}"


def _head(text: str) -> str:
    """The first word of a line of code: which line a correction looks like a fix for."""
    return re.split(r"[ (.=:]", text.strip())[0]


@pytest.mark.parametrize("a", ASSESSED_FIXES, ids=lambda a: str(a.id))
def test_the_faulty_line_is_not_the_only_one_with_two_corrections(a: ActivityFixture) -> None:
    """In 621, 622 and 1702 the faulty line was the only one with two candidate corrections, and
    in 1703 two of three corrections rewrote it, so counting the corrections found the bug (#223
    review, Should fix 4). Another line has as many candidates as the faulty one."""
    fixed = {i for x in a.solution["order"] for i in (x if isinstance(x, list) else [x])}
    lines = {x["id"]: x["text"] for x in a.config["lines"]}
    faulty = {_head(lines[i]) for i in lines if i not in fixed}
    candidates = Counter(_head(c["text"]) for c in a.config["corrections"])
    most_on_faulty = max(candidates[h] for h in faulty)
    elsewhere = max((n for h, n in candidates.items() if h not in faulty), default=0)
    assert elsewhere >= most_on_faulty >= 2, (a.id, candidates)


@pytest.mark.parametrize("a", ASSESSED_FIXES, ids=lambda a: str(a.id))
def test_hints_1_and_2_of_an_assessed_fix_are_about_what_the_program_does(
    a: ActivityFixture,
) -> None:
    """Module 6 counts an answer after hints 1 and 2 as met independently, and "Look at the line
    that loops over v's neighbours" located the bug for the student (#223 review, Should fix 4).
    Hints 1 and 2 talk about the output; neither points at a line or quotes the code."""
    fixed = {i for x in a.solution["order"] for i in (x if isinstance(x, list) else [x])}
    faulty = [x["text"].strip() for x in a.config["lines"] if x["id"] not in fixed]
    for hint in a.hints[:2]:
        low = hint.body.lower()
        assert "line" not in low, (a.id, hint.body)
        for text in faulty:
            assert text.lower() not in low, (a.id, hint.body)
        assert not re.search(r"queue\.\w|found =|graph\.adjacency|\bif n\b", hint.body), hint.body


@pytest.mark.parametrize("a", MASTERY + REVIEWS, ids=lambda a: str(a.id))
def test_alphabetical_order_is_never_called_a_rule_of_bfs(a: ActivityFixture) -> None:
    """Module 4 teaches that alphabetical order is a choice the course makes, not a rule of BFS
    (473, 461, 462); 621 and 619 said BFS must take neighbours alphabetically (review 13 Nov,
    High 4)."""
    for text in everything([a.config, a.solution, [h.body for h in a.hints]]):
        low = text.lower()
        assert "must take neighbours in alphabetical" not in low, a.id
        assert not re.search(
            r"(?<!our )\bbfs (takes|orders) (each vertex's |the )?neighbours"
            r"[^.]*alphabetical",
            low,
        ), (a.id, text)


@pytest.mark.parametrize(
    "a", [a for a in MASTERY if a.kind == "choose_tests"], ids=lambda a: str(a.id)
)
def test_a_mastery_choose_tests_item_is_not_a_practice_one(a: ActivityFixture) -> None:
    """623 and 624 were 506 and 507: the same faulty code and half the same test graphs, with the
    verdicts module 5's feedback had already given (#214 C2)."""

    def graphs(x: ActivityFixture) -> set[tuple[Any, ...]]:
        return {
            graph_key(t["directed"], t["vertices"], t["edges"], t["start_vertex"])
            for t in x.config["tests"]
        }

    for p in (p for p in PRACTICE if p.kind == "choose_tests"):
        assert a.config["code"] != p.config["code"], p.id
        assert len(graphs(a) & graphs(p)) <= 1, p.id


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
        # Its answers are marked right or wrong and earn points: they just count for no result.
        assert "nothing here is marked" not in (s.body or "").lower(), s.id


# The segment that gains attention in each module (Gagné's event 1): the module's first text or
# worked-example segment, which opens with a question. Modules 2 and 4 start with a video that
# may not be recorded yet, so their hook opens the worked example after it; module 3's hook is
# its first video (the campus puzzle). Module 5 opens with a video then a worked example (501)
# that leads straight into a practice activity. No segment is added for a hook: saved progress
# is a segment index, so a new segment would move every student.
HOOKS = {0: 1, 1: 101, 2: 204, 3: 313, 4: 404, 5: 501, 6: 601}


def test_every_module_with_content_opens_by_gaining_attention() -> None:
    for m in CONTENT.modules:
        if not m.segments:
            assert m.id not in HOOKS
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
            return len(line_ids(a.solution["order"]))  # groups (#145) count each line
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


# Option ids from staging whose text changed meaning in #147, or that left an item. They are
# retired, never reused: an old attempt's `selected` must not be read as new text (the lesson of
# #117 and #133). Ids made on this branch were never deployed, so they aren't listed.
RETIRED = {
    # Objective 3 (#214 C1): new situations whose direction must be worked out, so every option
    # is new text under a new id.
    610: {"a", "b", "c"},
    611: {"a", "b", "c"},
    612: {"a", "b", "c"},
    613: {"a", "b", "c"},
    1301: {"a", "b", "c"},
    1302: {"a", "b", "c"},
    1303: {"a", "b", "c"},
    1304: {"a", "b", "c"},
    1305: {"a", "b", "c"},
    316: {"a", "b", "c"},  # a new closing task (#214 C3): routes from E, not a count from A
    # Objective 1 (#214 C5): examples to classify instead of the definition's own words.
    601: {"a", "b"},
    602: {"a", "b"},
    604: {"a", "b", "c"},
    1102: {"a", "b"},
    1103: {"a", "b", "c"},
    1105: {"a", "b", "c"},
    614: {"a", "b", "c"},  # a new question: every staging id, the key's included
    615: {"c"},
    616: {"c"},
    617: {"b"},
    1402: {"b", "c"},
    1403: {"c"},
    1404: {"a", "b", "c"},  # a new question: every staging id, the key's included
    1405: {"c"},
    1601: {"a", "b"},
    # 625 claimed a cycle shows the visited-too-late bug; 623's directed cycle doesn't (round 2
    # review of #215, content 1). The key is now two routes to one vertex, under a new id.
    625: {"cycle"},
}


def test_a_retired_option_id_is_never_reused() -> None:
    for activity_id, retired in RETIRED.items():
        if activity_id in RETIRED_ACTIVITIES:
            continue  # the whole activity is gone, and its id is never reused
        options = {o["id"] for o in ACTIVITIES[activity_id].config["options"]}
        assert not retired & options, activity_id


# --- Items don't answer each other (#136 review) -------------------------------------------------


def graph_key(directed: bool, vertices: Any, edges: Any, start: str) -> tuple[Any, ...]:
    pairs = (
        (e["source"], e["target"]) if directed else tuple(sorted((e["source"], e["target"])))
        for e in edges
    )
    return (directed, frozenset(vertices), frozenset(pairs), start)


TRACES = [a for a in CONTENT.activities if a.kind == "trace"]


@pytest.mark.parametrize("a", TRACES, ids=lambda a: str(a.id))
def test_a_trace_graph_is_shown_nowhere_else(a: ActivityFixture) -> None:
    """A choose-tests case prints its graph's expected order, which is a trace's Order column:
    618 was the "sports-centre" case and 1502 the "residence" one."""
    c = a.config
    mine = graph_key(c.get("directed", False), c["vertices"], c["edges"], c["start_vertex"])
    for other in CONTENT.activities:
        if other.kind == "choose_tests":
            for t in other.config["tests"]:
                key = graph_key(t["directed"], t["vertices"], t["edges"], t["start_vertex"])
                assert key != mine, (other.id, t["id"])
        if other.kind == "trace" and other.id != a.id:
            oc = other.config
            key = graph_key(
                oc.get("directed", False), oc["vertices"], oc["edges"], oc["start_vertex"]
            )
            assert key != mine, other.id
    for g in CONTENT.graphs:
        key = graph_key(g.directed, g.vertices, [e.model_dump() for e in g.edges], g.start_vertex)
        assert key != mine, g.name
    # Nor does any other item, or any segment, spell out its order.
    order = ", ".join(run_bfs(GraphScenarioOut(id=0, name="", **dict(c))).order)
    for where, text in everything_shown():
        if not where.startswith(f"activity {a.id} "):
            assert order not in text, where


def test_no_two_choose_tests_items_have_the_same_answer() -> None:
    """624's feedback answered 1705: the same bug, so the same failing cases (#136)."""
    seen: dict[frozenset[str], int] = {}
    for a in (a for a in CONTENT.activities if a.kind == "choose_tests"):
        exposing = frozenset(a.solution["exposing"])
        assert exposing not in seen, (a.id, seen.get(exposing))
        seen[exposing] = a.id


FIXES = [a for a in CONTENT.activities if a.kind == "fix_the_bug"]


def line_ids(order: list[Any]) -> list[int]:
    """The line ids of an order, flattening any group of interchangeable lines (#145)."""
    return [i for x in order for i in (x if isinstance(x, list) else [x])]


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_the_first_correction_listed_is_never_a_right_one(a: ActivityFixture) -> None:
    """ "Always take the first correction" got every fix-the-bug item right on staging, and
    objective 7's rule (all parts) with it."""
    first = a.config["corrections"][0]["id"]
    assert first not in line_ids(a.solution["order"])


def test_right_corrections_are_not_in_one_place() -> None:
    places = {
        [c["id"] for c in a.config["corrections"]].index(i)
        for a in FIXES
        for i in line_ids(a.solution["order"])
        if i in {c["id"] for c in a.config["corrections"]}
    }
    assert len(places) > 1


def test_a_retired_correction_id_is_never_reused() -> None:
    """1703's correction 22 was a harmless extra condition; its replacement breaks BFS, a different
    meaning, so it has a new id (23) and 22 is retired. 621's corrections went with its old bug."""
    for activity_id, retired in RETIRED_CORRECTIONS.items():
        if activity_id in RETIRED_ACTIVITIES:
            continue  # the whole activity is gone, and its id is never reused
        a = ACTIVITIES[activity_id]
        used = {c["id"] for c in a.config["corrections"]} | {x["id"] for x in a.config["lines"]}
        assert not retired & used, activity_id


# --- The round-2 review's strategy search (#147) --------------------------------------------------
# Each ranker scores an option from what a student sees: its label, its id, where it is, the
# prompt and hints 1-2. A strategy is one ranker, or two or three applied in turn to break ties
# (then the earlier option). About 3,000 strategies; none may meet an objective's rule in module 6
# or in a review path's fresh items. Haladyna, Downing & Rodriguez (2002): keep the key's position,
# length and wording from cueing it, and avoid option pairs that point at the key.

RSQUO = "\N{RIGHT SINGLE QUOTATION MARK}"
DASH = "\N{EN DASH}"
WORDS = re.compile(rf"[a-z{RSQUO}'-]+")
ABSOLUTES = {
    "always",
    "never",
    "only",
    "every",
    "all",
    f"can{RSQUO}t",
    "can't",
    "cannot",
    "any",
    "everyone",
    "none",
}
JARGON = {
    "vertex",
    "vertices",
    "edge",
    "edges",
    "fewest",
    "ring",
    "queue",
    "reach",
    "reaches",
    "connections",
    "traversal",
    "path",
    "graph",
    "directed",
    "undirected",
}


def _words(text: str) -> list[str]:
    return WORDS.findall(text.lower())


def _jaccard(x: str, y: str) -> float:
    a, b = set(_words(x)), set(_words(y))
    return len(a & b) / max(1, len(a | b))


def _first(label: str) -> str:
    return (_words(label) or [""])[0]


def _rank_table(a: ActivityFixture) -> dict[str, list[float]]:
    opts = a.config["options"]
    n = len(opts)
    labels = [o["label"] for o in opts]
    firsts = [_first(t) for t in labels]
    prompt = set(_words(a.config["prompt"]))
    hints = set(_words(" ".join(h.body for h in a.hints if h.level <= 2)))
    near = [
        sum(_jaccard(t, u) for j, u in enumerate(labels) if j != i) for i, t in enumerate(labels)
    ]
    rows: dict[str, list[float]] = {
        "pos0": [-i for i in range(n)],
        "pos1": [-abs(i - 1) for i in range(n)],
        "pos2": [-abs(i - 2) for i in range(n)],
        "last": list(range(n)),
        "middle": [-abs(i - (n - 1) / 2) for i in range(n)],
        "longest": [len(t) for t in labels],
        "shortest": [-len(t) for t in labels],
        "most words": [len(_words(t)) for t in labels],
        "odd first word": [-firsts.count(f) for f in firsts],
        "majority first word": [firsts.count(f) for f in firsts],
        "nearest": near,
        "farthest": [-x for x in near],
        "prompt overlap": [len(set(_words(t)) & prompt) for t in labels],
        "prompt jaccard": [_jaccard(t, a.config["prompt"]) for t in labels],
        "hint overlap": [len(set(_words(t)) & hints) for t in labels],
        "fewest absolutes": [-sum(w in ABSOLUTES for w in _words(t)) for t in labels],
        "most absolutes": [sum(w in ABSOLUTES for w in _words(t)) for t in labels],
        "jargon": [sum(w in JARGON for w in _words(t)) for t in labels],
        "no because": [float("because" not in t) for t in labels],
        "has comma": [float("," in t) for t in labels],
        "yes": [float(f == "yes") for f in firsts],
        "no": [float(f == "no") for f in firsts],
        "short first sentence": [-len(t.split(".")[0]) for t in labels],
    }
    for letter in "abcd":
        rows[f"id {letter}"] = [float(o["id"] == letter) for o in opts]
    rows["not id d"] = [float(o["id"] != "d") for o in opts]
    return rows


RANKERS = list(_rank_table(next(a for a in CONTENT.activities if a.kind == "multiple_choice")))
GATES = [
    "majority first word",
    "odd first word",
    "yes",
    "no",
    "not id d",
    "fewest absolutes",
    "jargon",
    "no because",
]
LAST = ["longest", "shortest", "pos0", "last", "nearest", "farthest", "prompt overlap"]
SEARCH = (
    [(r,) for r in RANKERS]
    + [(x, y) for x in RANKERS for y in RANKERS if x != y]
    + [(x, y, z) for x in GATES for y in RANKERS for z in LAST if len({x, y, z}) == 3]
)


def _picks(where: str, strategies: Sequence[tuple[str, ...]]) -> list[dict[int, str]]:
    """For each strategy, the option it picks in each multiple-choice item of the set."""
    out = []
    tables = {a.id: _rank_table(a) for a in CHECK_SETS[where] if a.kind == "multiple_choice"}
    for strategy in strategies:
        chosen = {}
        for a in CHECK_SETS[where]:
            if a.kind != "multiple_choice":
                continue
            t, n = tables[a.id], len(a.config["options"])

            def rank(i: int, t: dict[str, list[float]] = t) -> tuple[float, ...]:
                return (*(t[r][i] for r in strategy), -i)  # noqa: B023 - used at once

            best = max(range(n), key=rank)
            chosen[a.id] = a.config["options"][best]["id"]
        out.append(chosen)
    return out


def _meeting(where: str, picks: list[dict[int, str]], keys: dict[int, str]) -> int:
    """How many strategies meet some objective's rule (real part counts) with these keys."""
    met = 0
    for chosen in picks:
        for objective, o in OBJECTIVES.items():
            items = [a for a in CHECK_SETS[where] if a.objective_id == objective]
            right = sum(chosen[a.id] == keys[a.id] for a in items if a.id in chosen)
            rule = Rule(pass_fraction=o.pass_fraction, max_wrong=o.max_wrong)
            if right and rule.met(right, sum(parts(a) for a in items)):
                met += 1
                break
    return met


@pytest.mark.parametrize("where", CHECK_SETS)
def test_no_single_surface_feature_meets_any_objective(where: str) -> None:
    """Any one of the rankers (position, id, length, first word, overlap, absolutes, jargon, …),
    used alone, leaves every objective not met."""
    single = [(r,) for r in RANKERS]
    picks = _picks(where, single)
    keys = {a.id: a.solution["correct"] for a in CHECK_SETS[where] if a.kind == "multiple_choice"}
    met = [single[i][0] for i, chosen in enumerate(picks) if _meeting(where, [chosen], keys)]
    assert not met, met


@pytest.mark.parametrize("where", CHECK_SETS)
def test_combined_strategies_do_no_better_than_chance(where: str) -> None:
    """The round-2 reviewer's search (rankers alone, in pairs and in three-ranker gates, about
    3,000 strategies) over four-item objectives always finds some combination that scores 3 of 4
    by luck. So the test compares with chance: the same strategies, the same texts, with each
    item's key moved to a random option. Fewer strategies may meet a rule with the real keys than
    with the median random keying; staging and round 2 were at chance (42% and 49% of draws)."""
    picks = _picks(where, SEARCH)
    mc = [a for a in CHECK_SETS[where] if a.kind == "multiple_choice"]
    real = _meeting(where, picks, {a.id: a.solution["correct"] for a in mc})
    rng = random.Random(147)  # noqa: S311 - a reproducible draw, not security
    draws = sorted(
        _meeting(where, picks, {a.id: rng.choice(a.config["options"])["id"] for a in mc})
        for _ in range(60)
    )
    assert real < draws[len(draws) // 2], (real, draws)


# --- Structure: no cue dimension left (round 3 review) ------------------------------------------

OBJ34 = [
    a
    for a in CONTENT.activities
    if a.kind == "multiple_choice"
    and a.objective_id in (3, 4)
    and a.purpose in ("mastery", "review")
]


@pytest.mark.parametrize("a", OBJ34, ids=lambda a: str(a.id))
def test_objective_3_and_4_options_are_about_the_same_length(a: ActivityFixture) -> None:
    """Haladyna et al. (2002): keep the options about equal in length, so length is no cue."""
    lengths = [len(o["label"]) for o in a.config["options"]]
    assert max(lengths) <= 1.15 * min(lengths), lengths


@pytest.mark.parametrize("objective", [3, 4])
@pytest.mark.parametrize("where", CHECK_SETS)
def test_the_keys_length_rank_varies(where: str, objective: int) -> None:
    longest = shortest = 0
    chosen = [
        a for a in CHECK_SETS[where] if a.objective_id == objective and a.kind == "multiple_choice"
    ]
    for a in chosen:
        lengths = {o["id"]: len(o["label"]) for o in a.config["options"]}
        key = lengths[a.solution["correct"]]
        longest += key == max(lengths.values())
        shortest += key == min(lengths.values())
    assert longest >= 1
    assert shortest >= 1
    items = len(chosen)
    assert longest < items - 1
    assert shortest < items - 1


def test_a_markers_first_word_does_not_predict_vertex_or_edge() -> None:
    """Edge markers used to open "what" and vertex markers never did (11 of 13 parts): the best
    rule from first word to vertex/edge is now no better than always guessing the commoner type."""
    for where, items in CHECK_SETS.items():
        pairs = [
            (
                item["label"].split(": ", 1)[1].split()[0].lower(),
                a.solution["pairs"][item["id"]].startswith("e"),
            )
            for a in items
            if a.objective_id == 2 and "Marker" in str(a.config["left"])
            for item in a.config["left"]
        ]
        by_word: dict[str, Counter[bool]] = {}
        for word, edge in pairs:
            by_word.setdefault(word, Counter())[edge] += 1
        best_rule = sum(max(c.values()) for c in by_word.values())
        always_commoner = max(Counter(edge for _, edge in pairs).values())
        assert best_rule <= always_commoner, (where, by_word)


# --- Code comments don't fill the blanks (#214 C15, round 2 review of #215) -----------------------
# What the comments in 205, 291 and 405 said: "an empty list" ([]), "unless v is already in" (not
# in), "the edge goes from a to b" (a, b), "back from b to a" (not self.directed), "the front of
# the queue" (popleft).
STATED = ("empty list", "unless", "from a to b", "back from b", "front of the queue")


@pytest.mark.parametrize(
    "a", [a for a in CONTENT.activities if a.kind == "fill_in"], ids=lambda a: str(a.id)
)
def test_no_code_comment_states_a_blank(a: ActivityFixture) -> None:
    for line in a.config["code"].splitlines():
        code, _, comment = line.partition("#")
        assert not (comment and "__" in code), line  # no comment beside a blank
        assert not any(phrase in comment.lower() for phrase in STATED), line


# --- No word or pattern only the keys share (round 2 review of #215, content 5) ----------------
# Only the right option said "since" in 611-613, only the right one wrote "Directed:" or
# "Undirected:" in 1302 and 1305, and only the right one said "ring" in 614, 628 and 1402. A
# student who noticed would pick the key without knowing why. Function words are left out: they
# carry no meaning a student could read as a cue.
FUNCTION_WORDS = {"a", "an", "the", "and", "or", "but", "for", "of", "to", "in", "on", "at", "by"}
FUNCTION_WORDS |= {
    "it",
    "its",
    "is",
    "are",
    "be",
    "so",
    "as",
    "if",
    "not",
    "no",
    "yes",
    "with",
    "there",
}
QUICK_CHECKS = {"quick checks": [a for a in CONTENT.activities if a.purpose == "test_out"]}


def cue_tokens(label: str) -> set[str]:
    """A label's words, each without a plural s, and how many colons it has (a colon after the
    verdict was 1302's and 1305's pattern)."""
    words = {w.removesuffix("s") for w in _words(label) if w not in FUNCTION_WORDS}
    return words | {f"{label.count(':')} colons"}


@pytest.mark.parametrize("where", [*CHECK_SETS, *QUICK_CHECKS])
def test_no_word_or_pattern_is_found_only_in_the_keys(where: str) -> None:
    items = {**CHECK_SETS, **QUICK_CHECKS}[where]
    in_keys: Counter[str] = Counter()
    in_wrong: Counter[str] = Counter()
    for a in (a for a in items if a.kind == "multiple_choice"):
        for o in a.config["options"]:
            right = o["id"] == a.solution["correct"]
            (in_keys if right else in_wrong).update(cue_tokens(o["label"]))
    tells = sorted(w for w, n in in_keys.items() if n >= 2 and not in_wrong[w])
    assert tells == [], where


# --- Same id, same meaning: staging's text, kept or listed -----------------------------------------

SNAPSHOT = json.loads((Path(__file__).parent / "data" / "staging_options.json").read_text("utf-8"))
# Same-id rewordings that keep the meaning (lengthened, shortened, or restated with the same claim),
# reviewed item by item in the PR body. Every other change of text needs a new id.
WORDING_ONLY = {
    "options": {
        (3, "b"),
        (312, "a"),
        (312, "b"),
        (312, "c"),
        (602, "c"),
        (605, "b"),
        (615, "a"),
        (615, "b"),
        (616, "a"),
        (616, "b"),
        (617, "a"),
        (617, "c"),
        (1101, "a"),
        (1106, "c"),
        (1401, "a"),
        (1401, "b"),
        (1401, "c"),  # the fewest bus rides, not changes: still the BFS problem (#214 C15)
        (1402, "a"),
        (1403, "a"),
        (1403, "b"),
        (1405, "a"),
        (1405, "b"),
        (1701, "b"),
        (1701, "c"),
        # The code's set is `found`, not `visited`, so "visited" means "has left the queue"
        # everywhere (review 13 Nov, High 3): the same line, renamed.
        (1601, "c"),
        (1702, "20"),
        (1703, "20"),
        (1703, "21"),
    },
    # An objective 2 marker now describes its part instead of naming it; it is the same part,
    # with the same answer, so an earlier pair means what it meant.
    "matching_left": {(a, m) for a in (606, 607, 608, 1202, 1203, 1204) for m in ("1", "2", "3")},
    # 102's definitions keep their meaning in new words, without the term's own word (#214 C6).
    # 313's reasons no longer share a word with their situation (round 2 review of #215, content 10).
    "matching_right": {(102, d) for d in ("d1", "d2", "d3", "d4")} | {(313, "r1"), (313, "r2")},
}
# Matching items that left an item: 609 and 1205 classify new situations by meaning (#214 C4), and
# 603 matches three terms instead of "graph" (#214 C5).
GONE_LEFT = (
    {
        (609, i)
        for i in (
            "phone-calls",
            "shared-walls-between-houses",
            "module-prerequisites",
            "two-way-radio-links",
        )
    }
    | {(603, "t1")}
    | {
        (1205, i)
        for i in (
            "emails",
            "train-tracks-between-stations",
            "teammates-in-a-project",
            "a-tournament",
        )
    }
)
# Right entries that left an item (#214): 603's family tree and stack of plates (C5), 105's random
# non-edges, now near misses, and 607's and 1204's vertices and edges, which named the places by
# their initials (C15).
GONE_RIGHT = (
    {(603, "e1"), (603, "e3")}
    | {(105, e) for e in ("AB", "DF", "FG")}
    | {(607, e) for e in ("vK", "vL", "vM", "vN", "eKL", "eKM", "eLN", "eMN")}
    | {(1204, e) for e in ("vR", "vS", "vT", "vU", "eRS", "eST", "eTU", "eSR", "eTS", "eUT")}
)
# Fix-the-bug corrections that left an item: 621 is a new bug (#214 C2), so all its corrections are.
# 621 (its 26, newer than the snapshot), 622 and 1702 each lost a correction that rewrote the
# faulty line again, for one that rewrites another line, so the corrections no longer point at
# the bug (review 13 Nov, High 10).
RETIRED_CORRECTIONS = {621: {20, 21, 22, 23}, 622: {21}, 1702: {22}, 1703: {22}}
# Ids that left an item; they must never come back (RETIRED, plus the retired corrections).
GONE = {(a, i) for a, ids in RETIRED.items() if a != 612 for i in ids} | {
    (a, str(i)) for a, ids in RETIRED_CORRECTIONS.items() if a != 621 for i in ids
}  # 612 and 621 left whole (RETIRED_ACTIVITIES below), not option by option
# Whole activities taken out of the course; their ids must never return with other content. 107,
# module 1's closing task, matched four situations against one shared list, so each situation's
# own nouns gave its answer away; it became four questions, 108-111, each with its own options,
# shown by fresh segments 114-117. Segment 110, which showed 107, is retired with it.
# 612, objective 3's house-building item, asked the student to recognise a model among four; it
# became 630, a matching item in which the student builds it: the jobs, the link, its direction
# and the kind of graph (review 13 Nov, High 10). Segment 613, which showed 612, is retired with it.
# 621, objective 7's first fix-the-bug item, had no real bug: its program took neighbours in the
# order their edges were added, still breadth-first, so it only broke the course's alphabetical
# convention. It became 631, whose loop takes the start's neighbours every time (#223 review,
# Should fix 6). Segment 622, which showed 621, is retired with it. A student's answer to 612 or 621
# stands in for 630 or 631 (app/services/mastery.py, REPLACES).
RETIRED_ACTIVITIES = {107, 612, 621}
RETIRED_SEGMENTS = {110, 613, 622}


def _now(a: ActivityFixture, kind: str) -> dict[str, str]:
    if kind == "options" and a.kind == "multiple_choice":
        return {o["id"]: o["label"] for o in a.config["options"]}
    if kind == "options":
        return {str(c["id"]): c["text"] for c in a.config["corrections"]}
    side = "left" if kind == "matching_left" else "right"
    return {o["id"]: o["label"] for o in a.config[side]}


@pytest.mark.parametrize("kind", ["options", "matching_left", "matching_right"])
def test_an_id_from_staging_keeps_its_text_unless_retired_or_listed(kind: str) -> None:
    changed, gone = set(), set()
    for activity_id, staged in SNAPSHOT[kind].items():
        if int(activity_id) in RETIRED_ACTIVITIES:
            assert int(activity_id) not in ACTIVITIES
            continue
        now = _now(ACTIVITIES[int(activity_id)], kind)
        for item_id, text in staged.items():
            if item_id not in now:
                gone.add((int(activity_id), item_id))
            elif now[item_id] != text:
                changed.add((int(activity_id), item_id))
    assert sorted(changed - WORDING_ONLY[kind]) == []
    assert sorted(WORDING_ONLY[kind] - changed) == []  # the list says only what is true
    assert gone == {"options": GONE, "matching_left": GONE_LEFT, "matching_right": GONE_RIGHT}[kind]


def test_a_retired_segment_id_is_never_reused() -> None:
    assert not RETIRED_SEGMENTS & {s.id for s in SEGMENTS}


def test_counting_the_places_a_marker_names_does_not_meet_objective_2() -> None:
    """One place named: a vertex; two: the edge between them; letters from the prompt's names. It
    scored every objective 2 marker on staging and in round 1 (#147)."""
    named = re.compile(r"(?:are|,|and|:)\s+(?:the\s+)?([^,():.]+?) \(([A-Z])\)")
    for where, items in CHECK_SETS.items():
        mine = [a for a in items if a.objective_id == 2]
        right = 0
        for a in (a for a in mine if a.kind == "matching" and "Marker" in str(a.config["left"])):
            names = {n.lower(): letter for n, letter in named.findall(a.config["prompt"])}
            labels = {r["id"]: r["label"] for r in a.config["right"]}
            for item in a.config["left"]:
                text = item["label"].lower()
                found = sorted((text.index(n), letter) for n, letter in names.items() if n in text)
                letters = [letter for _, letter in found]
                guess = f"Vertex {letters[0]}" if len(letters) == 1 else None
                if len(letters) == 2:
                    u, v = letters
                    guess = next(
                        (
                            lab
                            for lab in labels.values()
                            if lab
                            in (f"Edge {u}{DASH}{v}", f"Edge {v}{DASH}{u}", f"Edge {u} → {v}")
                        ),
                        None,
                    )
                right += guess == labels[a.solution["pairs"][item["id"]]]
        o = OBJECTIVES[2]
        rule = Rule(pass_fraction=o.pass_fraction, max_wrong=o.max_wrong)
        # The classifying item (609, 1205) is given to the strategy as all right.
        right += sum(len(a.config["left"]) for a in mine if "Marker" not in str(a.config["left"]))
        assert not rule.met(right, sum(parts(a) for a in mine)), (where, right)


# --- Module 1's closing task (108-111): no surface rule answers it ----------------------------------

CLOSING = [ACTIVITIES[i] for i in (108, 109, 110, 111)]
MODEL = re.compile(r"Vertices: (?:the )?(.+?)\. Edges: (?:the )?(.+?)\. (Directed|Undirected)\b")
DIRECTION_STATED = {
    "Undirected": re.compile(r"both ways|both directions", re.I),
    "Directed": re.compile(r"n't \w+ back|hasn't|doesn't|one way|no link", re.I),
}


def _model(label: str) -> tuple[str, str, str]:
    found = MODEL.match(label)
    assert found, label
    return found.group(1), found.group(2), found.group(3)


def _at(noun: str, prompt: str) -> int | None:
    """Where the prompt first names this option noun (by its first word's stem), if it does."""
    found = re.search(rf"\b{re.escape(noun.split()[0][:5])}", prompt, re.I)
    return found.start() if found else None


def _key(a: ActivityFixture) -> tuple[str, str, str]:
    return _model(next(o["label"] for o in a.config["options"] if o["id"] == a.solution["correct"]))


def _stated_direction(a: ActivityFixture) -> str | None:
    said = [d for d, pattern in DIRECTION_STATED.items() if pattern.search(a.config["prompt"])]
    return said[0] if len(said) == 1 else None


def _by_noun_order(a: ActivityFixture, vertex_first: bool) -> str | None:
    """A reader who takes the first (or second) noun the prompt names as the vertices, the other
    as the edges, and copies the direction the prompt states. None when it can't decide."""
    nouns = {n for o in a.config["options"] for n in _model(o["label"])[:2]}
    placed = sorted((at, n) for n in nouns if (at := _at(n, a.config["prompt"])) is not None)
    direction = _stated_direction(a)
    if len(placed) < 2 or direction is None:
        return None
    first, second = placed[0][1], placed[1][1]
    v, e = (first, second) if vertex_first else (second, first)
    return next(
        (o["id"] for o in a.config["options"] if _model(o["label"]) == (v, e, direction)), None
    )


def _shortest(a: ActivityFixture) -> str:
    """The shortest option. A tie that includes the key counts as the key: a reader choosing among
    the shortest options can land on it."""
    least = min(len(o["label"]) for o in a.config["options"])
    tied = [str(o["id"]) for o in a.config["options"] if len(o["label"]) == least]
    return a.solution["correct"] if a.solution["correct"] in tied else tied[0]


CLOSING_RULES: dict[str, Callable[[ActivityFixture], str | None]] = {
    "first noun is the vertices, copy the stated direction": lambda a: _by_noun_order(a, True),
    "second noun is the vertices, copy the stated direction": lambda a: _by_noun_order(a, False),
    "most like the rest": most_like_the_rest,
    "nearest to the other options": nearest_to_the_others,
    "the longest option": longest,
    "the shortest option": _shortest,
}


@pytest.mark.parametrize("rule", CLOSING_RULES)
def test_no_surface_rule_answers_module_1s_closing_task(rule: str) -> None:
    """The first version scored 4 of 4 by "first noun = vertices, second = edges, copy the stated
    direction", and convergence picked the key in two items (content audit, 13 Nov, section 7)."""
    pick = CLOSING_RULES[rule]
    right = [a.id for a in CLOSING if pick(a) == a.solution["correct"]]
    assert len(right) <= 1, (rule, right)


def test_the_closing_task_varies_noun_order_direction_and_key_position() -> None:
    vertex_first = []
    for a in CLOSING:
        v, e, _ = _key(a)
        at_v, at_e = _at(v, a.config["prompt"]), _at(e, a.config["prompt"])
        assert at_v is not None, a.id
        assert at_e is not None, a.id
        vertex_first.append(at_v < at_e)
    assert any(vertex_first), vertex_first
    assert not all(vertex_first), vertex_first
    # The direction is worked out from what the connection means in at least two items.
    assert sum(_stated_direction(a) is None for a in CLOSING) >= 2
    assert len({right_index(a) for a in CLOSING}) >= 3
    # Each model is offered once: exactly one option is right.
    for a in CLOSING:
        models = [_model(o["label"]) for o in a.config["options"]]
        key = _model(
            next(o["label"] for o in a.config["options"] if o["id"] == a.solution["correct"])
        )
        assert models.count(key) == 1, a.id


def test_the_closing_hints_climb_from_a_question_to_the_explained_answer() -> None:
    """Level 1 asks what to look for, level 2 is a general rule naming none of the item's nouns,
    level 3 gives part of the answer but not the direction, and level 4 is the answer with why
    (ID document §7.5). The first version named the vertices and edges at levels 1 and 2."""
    for a in CLOSING:
        hints = {h.level: h.body for h in a.hints}
        v, e, direction = _key(a)
        nouns = {n for o in a.config["options"] for n in _model(o["label"])[:2]}
        assert hints[1].endswith("?"), a.id
        assert not any(_at(n, hints[2]) is not None for n in nouns), (a.id, hints[2])
        assert direction.lower() not in hints[3].lower(), a.id
        assert hints[4].startswith(f"Answer: Vertices: {v}. Edges: {e}. {direction}."), a.id
        assert len(re.findall(r"[.!?](?:\s|$)", hints[4])) >= 5, a.id  # the answer, then why


def test_the_handshake_item_agrees_with_the_video_on_mutual_connections() -> None:
    """Segment 108 teaches that a mutual follow is two arrows, so still directed. The handshake is
    undirected because it can't happen one way only: the reverse always exists. That is the one
    question module 1 teaches for direction ("must the reverse exist too?", 193). The second version
    counted "acts", which taught nowhere else and sounded like 193's trap, "two people are involved
    in each act" (round 2 review of #213)."""
    video = next(s for s in SEGMENTS if s.id == 108)
    assert "two arrows" in (video.body or "")
    a = ACTIVITIES[111]
    assert _key(a)[2] == "Undirected"
    assert "each has shaken the other" not in a.config["prompt"]
    two_arrows = next(o["id"] for o in a.config["options"] if "arrow each way" in o["label"])
    for text in (a.solution["feedback"][two_arrows], a.solution["explanation"]):
        assert "two arrows that both happen to exist" in text, text
    assert "reverse" in a.solution["feedback"][two_arrows]
    for where, text in shown_text(a):
        assert not {"act", "acts", "shared", "together"} & set(_words(text)), (where, text)
    # Not having shaken hands is not the same as not having met.
    assert not any("met" in _words(t) for _, t in shown_text(a))
