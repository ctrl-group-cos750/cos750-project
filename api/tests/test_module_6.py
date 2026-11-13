"""Module 6 (Mastery check and report, #28): every answer the mastery items hold is really right.

Module 6 decides each objective's result (app/services/mastery.py), and a review path's fresh
items decide it again after a "not yet" (review.json). So for both sets of items this checks:
each objective has enough parts for its rule (Table 1 of the ID document) to mean something;
every trace answer and hint is the engine's (app/services/bfs.py); the code items, filled in
or fixed with their answers, pass the hidden tests from the design, and every wrong token,
distractor line or faulty line really fails one; every choose-tests answer is what the faulty
version actually does; and every labelling and classifying answer is the graph the prompt
describes. Plus the content rules: four hint levels, the last giving the answer, and feedback
on every wrong answer.

The code here is our own fixture content, run in our own tests. A student's code never runs:
their answers are only compared with these solutions (app/services/checking.py).
"""

import re
import signal
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import combinations, product
from types import FrameType
from typing import Any

import pytest
from parsons_orders import runnable_orders

from app.schemas.activities import FixTheBugSolution, ParsonsSolution
from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, ReviewPathFixture, read_fixtures
from app.services.bfs import run_bfs
from app.services.checking import check_activity
from app.services.mastery import MASTERY_MODULE, Rule

CONTENT: FixtureFile = read_fixtures()
ACTIVITIES = {a.id: a for a in CONTENT.activities}
MODULE = next(m for m in CONTENT.modules if m.id == MASTERY_MODULE)
OBJECTIVES = {o.id: o for o in CONTENT.objectives}
PATHS: dict[int, ReviewPathFixture] = {r.objective_id: r for r in CONTENT.review_paths}
CHECK = [ACTIVITIES[s.activity_id] for s in MODULE.segments if s.activity_id is not None]
FRESH = {
    o: [
        ACTIVITIES[s.activity_id]
        for s in p.segments
        if s.activity_id is not None and ACTIVITIES[s.activity_id].purpose == "mastery"
    ]
    for o, p in PATHS.items()
}
PRACTICE = [
    ACTIVITIES[s.activity_id]
    for p in PATHS.values()
    for s in p.segments
    if s.activity_id is not None and ACTIVITIES[s.activity_id].purpose == "review"
]
EVERY = CHECK + [a for items in FRESH.values() for a in items] + PRACTICE
SETS = [("module 6", o) for o in OBJECTIVES] + [("review path", o) for o in OBJECTIVES]
BLANK = re.compile(r"__(\d+)__")
DASH = "\N{EN DASH}"
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|→) ?([A-Z])\b")

# The Graph class the code items run on (module 2's finished class, as in the design).
GRAPH = """
class Graph:
    def __init__(self, directed=False):
        self.directed = directed
        self.adjacency = {}

    def add_vertex(self, v):
        if v not in self.adjacency:
            self.adjacency[v] = []

    def add_edge(self, a, b):
        self.add_vertex(a)
        self.add_vertex(b)
        self.adjacency[a].append(b)
        if not self.directed:
            self.adjacency[b].append(a)
"""

# The hidden tests from the design (his module.json): (graph, start). The expected order is the
# engine's, so a test also fails on a repeated vertex or on returning anything but that list.
HIDDEN: dict[str, tuple[bool, str, list[str], str]] = {
    # name: (directed, vertices, edges in the order they are added, start)
    "line": (False, "VWXYZ", ["ZY", "YX", "XW", "WV"], "X"),
    "cycle": (False, "ABCD", ["AB", "BC", "CD", "DA", "AC"], "A"),
    "sports-centre": (False, "ABCDEFG", ["AB", "AD", "BC", "BE", "DE", "EF", "CG", "FG"], "A"),
    "sports-centre-from-g": (
        False,
        "ABCDEFG",
        ["AB", "AD", "BC", "BE", "DE", "EF", "CG", "FG"],
        "G",
    ),
    "residence": (False, "PQRSTU", ["PQ", "PR", "QS", "RS", "RT", "SU", "TU"], "P"),
    "residence-from-u": (False, "PQRSTU", ["PQ", "PR", "QS", "RS", "RT", "SU", "TU"], "U"),
    "out-of-order": (False, "ABCDE", ["AE", "AC", "AB", "BD"], "A"),
    "two-islands": (False, "ABCDE", ["AB", "BC", "DE"], "A"),
    "one-way": (True, "ABCD", ["AB", "BC", "CA", "DA"], "A"),
}


def scenario(directed: bool, vertices: Any, edges: Any, start: str) -> GraphScenarioOut:
    return GraphScenarioOut(
        id=0,
        name="",
        directed=directed,
        vertices=list(vertices),
        edges=[GraphEdge(source=e[0], target=e[1]) for e in edges],
        start_vertex=start,
    )


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """A wrong line can make BFS loop for ever (a visited set that is emptied again): stop it."""

    def stop(signum: int, frame: FrameType | None) -> None:
        raise TimeoutError

    previous = signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def run_bfs_code(code: str, directed: bool, vertices: Any, edges: Any, start: str) -> Any:
    """What `bfs` in `code` returns on this graph, or the exception it raised (a loop that never
    ends included)."""
    namespace: dict[str, Any] = {}
    try:
        with time_limit(0.5):
            return _run(code, namespace, directed, vertices, edges, start)
    except Exception as exc:  # any error is a failing test
        return exc


def _run(
    code: str, namespace: dict[str, Any], directed: bool, vertices: Any, edges: Any, start: str
) -> Any:
    exec(GRAPH + "\n" + code, namespace)  # noqa: S102 - our own fixture code, in our own tests
    g = namespace["Graph"](directed=directed)
    for v in vertices:
        g.add_vertex(v)
    for source, target in edges:
        g.add_edge(source, target)
    return namespace["bfs"](g, start)


def passes_hidden(code: str) -> bool:
    for directed, vertices, edges, start in HIDDEN.values():
        want = run_bfs(scenario(directed, vertices, edges, start)).order
        if run_bfs_code(code, directed, vertices, edges, start) != want:
            return False
    return True


def parts(a: ActivityFixture) -> int:
    """How many parts the checker grades, which the mastery rule counts (app/services/mastery.py)."""
    match a.kind:
        case "multiple_choice":
            return 1
        case "matching":
            return len(a.config["left"])
        case "trace":
            config = dict(a.config)
            return len(run_bfs(GraphScenarioOut(id=0, name="", **config)).steps)
        case "parsons" | "fix_the_bug":
            return len(first_order(a))
        case "fill_in":
            return len(a.config["blanks"])
        case "choose_tests":
            return len(a.config["tests"])
    raise AssertionError(a.kind)


def items_of(where: str, objective: int) -> list[ActivityFixture]:
    if where == "module 6":
        return [a for a in CHECK if a.objective_id == objective]
    return FRESH[objective]


def first_order(a: ActivityFixture) -> list[int]:
    """One correct order of a Parsons or fix-the-bug item's lines (its `order`, groups as
    written)."""
    shape = FixTheBugSolution if a.kind == "fix_the_bug" else ParsonsSolution
    return shape.model_validate(a.solution).first_order()


def lines_text(a: ActivityFixture, order: list[int]) -> str:
    by_id = {x["id"]: x["text"] for x in a.config["lines"] + a.config.get("corrections", [])}
    return "\n".join(by_id[i] for i in order)


def filled(a: ActivityFixture, **changes: str) -> str:
    answers = {str(k): v for k, v in a.solution["answers"].items()} | changes
    return BLANK.sub(lambda m: answers[m.group(1)], a.config["code"])


# --- What the check holds ------------------------------------------------------------------------


def test_module_6_opens_with_what_the_check_is_then_only_mastery_items() -> None:
    first, *rest = MODULE.segments
    assert first.kind == "text"
    assert "first answer" in first.body
    assert all(s.kind == "activity" for s in rest)
    assert all(a.purpose == "mastery" and a.module_id == MASTERY_MODULE for a in CHECK)
    # Its recall question is asked before the segments (FR-2.4), not in one.
    recall = [a.id for a in CONTENT.activities if a.module_id == 6 and a.purpose == "retrieval"]
    assert recall == [625]
    assert sorted(a.id for a in CHECK) == sorted(
        a.id for a in CONTENT.activities if a.module_id == 6 and a.id not in recall
    )


def test_activity_ids_are_in_their_ranges() -> None:
    # 601-624, then objective 8's 626-629 (#70): 625 was already a module 6 retrieval item.
    assert [a.id for a in CHECK] == [*range(601, 625), *range(626, 630)]
    for o, path in PATHS.items():
        base = 1000 + 100 * o
        assert all(base < s.id < base + 100 for s in path.segments)
        assert all(base < a.id < base + 100 for a in FRESH[o])


@pytest.mark.parametrize(("where", "objective"), SETS)
def test_each_objective_has_enough_parts_for_its_rule(where: str, objective: int) -> None:
    """Table 1's criteria, counted over parts: 4 of 5 (0.8) needs at least 5 parts, 3 of 4 (0.75)
    at least 4, and "at most one error" on a trace of 6 to 8 vertices at least 6. With fewer,
    one slip would already be a "not yet", which is not what the criterion says."""
    o = OBJECTIVES[objective]
    items = items_of(where, objective)
    assert items, f"{where} has no item for objective {objective}"
    total = sum(parts(a) for a in items)
    if o.max_wrong is not None:
        assert 6 <= total <= 8
        assert Rule(max_wrong=o.max_wrong).met(total - 1, total)
    elif o.pass_fraction == 1.0:
        assert total >= 1
    else:
        assert o.pass_fraction is not None
        assert total >= round(1 / (1 - o.pass_fraction))
        assert Rule(pass_fraction=o.pass_fraction).met(total - 1, total)


def test_the_kinds_follow_table_1() -> None:
    kinds = {o: sorted({a.kind for a in items_of("module 6", o)}) for o in OBJECTIVES}
    assert kinds == {
        1: ["matching", "multiple_choice"],
        2: ["matching"],
        3: ["multiple_choice"],
        4: ["multiple_choice"],
        5: ["trace"],
        6: ["fill_in", "parsons"],
        7: ["choose_tests", "fix_the_bug"],
        8: ["multiple_choice"],
    }
    # Objective 2: three diagrams labelled, four graphs classified.
    assert [len(a.config["left"]) for a in items_of("module 6", 2)] == [3, 3, 3, 4]


def test_the_fresh_items_are_not_the_module_6_items() -> None:
    def seen(a: ActivityFixture) -> str:
        return (
            str(a.config.get("prompt", ""))
            + str(a.config.get("left", ""))
            + str(a.config.get("code", ""))
            + str(a.config.get("vertices", ""))
            + str(a.config.get("lines", ""))  # a Parsons item shows only its lines
        )

    check = {seen(a) for a in CHECK}
    assert not check & {seen(a) for items in FRESH.values() for a in items}


def test_the_right_option_is_not_always_in_the_same_place() -> None:
    places = Counter(
        [o["id"] for o in a.config["options"]].index(a.solution["correct"])
        for a in EVERY
        if a.kind == "multiple_choice"
    )
    assert len(places) >= 3  # objective 3's items have four options
    assert max(places.values()) <= 0.5 * sum(places.values())


@pytest.mark.parametrize("a", EVERY, ids=lambda a: str(a.id))
def test_every_item_has_four_hint_levels_and_the_last_gives_the_answer(a: ActivityFixture) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")
    for text in [h.body for h in a.hints] + [str(a.config.get("prompt", ""))]:
        assert "**" not in text  # shown as plain text
        assert "`" not in text


@pytest.mark.parametrize("a", EVERY, ids=lambda a: str(a.id))
def test_every_wrong_answer_has_feedback(a: ActivityFixture) -> None:
    fb = a.solution.get("feedback", {})
    match a.kind:
        case "multiple_choice":
            wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
            assert set(fb) == wrong
        case "matching":
            assert set(fb) == {item["id"] for item in a.config["left"]}
        case "fill_in":
            wrong = set(a.config["options"]) - set(a.solution["answers"].values())
            assert {t for messages in fb.values() for t in messages} == wrong
        case "fix_the_bug":
            faulty = {x["id"] for x in a.config["lines"]} - set(first_order(a))
            assert {int(k) for k in fb} == faulty
        case "choose_tests":
            assert set(fb) == {t["id"] for t in a.config["tests"]}
        case "trace":
            pass  # the trace checker's messages are its own (app/services/checking.py)


# --- Objective 1 to 4: the answers ----------------------------------------------------------------


def right_label(a: ActivityFixture, left_id: str) -> str:
    right_id = a.solution["pairs"][left_id]
    return str(next(r["label"] for r in a.config["right"] if r["id"] == right_id))


LABELLING = [
    a
    for a in EVERY
    if a.objective_id == 2 and a.kind == "matching" and "Marker" in str(a.config["left"])
]
CLASSIFYING = [
    a for a in EVERY if a.objective_id == 2 and a.kind == "matching" and a not in LABELLING
]


def test_objective_2_has_three_labelling_items_and_one_classifying_item_in_each_set() -> None:
    mastery = [a for a in LABELLING + CLASSIFYING if a.purpose == "mastery"]
    assert len([a for a in mastery if a in LABELLING]) == 6
    assert len([a for a in mastery if a in CLASSIFYING]) == 2


NAMED = re.compile(r"(?:are|,|and|:)\s+(?:the\s+)?([^,():.]+?) \(([A-Z])\)")


def named_part(prompt: str, marker: str) -> str:
    """The part a marker describes, worked out from the names and edges the prompt lists. A marker
    names a thing or what joins two things, as practice item 104 does, but how many places it
    names doesn't say whether the answer is a vertex or an edge (#147): "the tap between the
    kitchen tap and the lawn tap" is a vertex, "what carries water to the shed tap" an edge."""
    letters = {name.lower(): letter for name, letter in NAMED.findall(prompt)}
    edges = {(u, arrow, v) for u, arrow, v in EDGE.findall(prompt)}
    directed = any(arrow == "→" for _, arrow, _ in edges)

    def letter(name: str) -> str:
        return str(letters[name.lower().removeprefix("the ").strip()])

    def touching(x: str) -> set[tuple[str, str, str]]:
        return {e for e in edges if x in (e[0], e[2])}

    def neighbours(x: str) -> set[str]:
        return {v if u == x else u for u, _, v in touching(x)}

    def edge(e: tuple[str, str, str]) -> str:
        u, arrow, v = e
        return f"Edge {u} → {v}" if arrow == "→" else f"Edge {u}{DASH}{v}"

    def only(found: set[Any]) -> Any:
        assert len(found) == 1, (marker, found)  # the marker picks out exactly one part
        return next(iter(found))

    text = marker.split(": ", 1)[1]
    if m := re.fullmatch(r"(?:what takes you one way|the road) from (.+) to (.+)", text):
        u, v = (letter(x) for x in m.groups())
        assert (u, "→", v) in edges, marker
        return f"Edge {u} → {v}"
    if m := re.fullmatch(
        r"(?:what joins|the \w+ between|the \w+ from) (.+?) (?:and|to) (.+)", text
    ):
        u, v = (letter(x) for x in m.groups())
        if (u, DASH, v) in edges or (v, DASH, u) in edges:
            return f"Edge {u}{DASH}{v}"
        return f"Vertex {only(neighbours(u) & neighbours(v))}"  # the tap between two taps
    if m := re.fullmatch(r"what the (.+)'s and the (.+)'s \w+ both lead to", text):
        u, v = (letter(x) for x in m.groups())
        return f"Vertex {only(neighbours(u) & neighbours(v))}"
    if m := re.fullmatch(r"what (?:carries water to|buses drive along to reach) (.+)", text):
        return edge(only(touching(letter(m.group(1)))))
    if m := re.fullmatch(r"(?:what you|the \w+ you) drive along to leave (.+)", text):
        x = letter(m.group(1))
        assert directed
        return edge(only({e for e in edges if e[0] == x}))
    if m := re.fullmatch(r"what you reach after driving on from (.+)", text):
        x = letter(m.group(1))
        return f"Vertex {only({e[2] for e in edges if e[0] == x})}"
    if m := re.fullmatch(r"the \w+ with a single \w+, which goes to (.+)", text):
        x = letter(m.group(1))
        return f"Vertex {only({y for y in set(letters.values()) if neighbours(y) == {x}})}"
    return f"Vertex {letter(text)}"


def same_part(a: str, b: str) -> bool:
    """An undirected edge is the same edge whichever end is named first."""
    if DASH in a and DASH in b:
        return set(a.removeprefix("Edge ").split(DASH)) == set(b.removeprefix("Edge ").split(DASH))
    return a == b


@pytest.mark.parametrize("a", LABELLING, ids=lambda a: str(a.id))
def test_each_marker_names_the_part_its_answer_names(a: ActivityFixture) -> None:
    prompt = a.config["prompt"]
    assert {arrow for _, arrow, _ in EDGE.findall(prompt)} in ({DASH}, {"→"})
    for item in a.config["left"]:
        answer = right_label(a, item["id"])
        assert same_part(answer, named_part(prompt, item["label"])), item["label"]
        # A marker gives no letter, and no "vertex"/"edge" word: the student works both out (#147).
        marker = item["label"].split(": ", 1)[1]
        assert not re.search(r"\b[A-Z]\b", marker), marker
        assert not re.search(r"vertex|edge", marker), marker
        assert "n't" not in marker  # no negation puzzles
        assert " not " not in marker
    # The answer hint says the same.
    for item in a.config["left"]:
        assert f"{item['id']} = {right_label(a, item['id'])}" in a.hints[-1].body


@pytest.mark.parametrize("a", CLASSIFYING, ids=lambda a: str(a.id))
def test_each_graph_is_classified_by_what_its_connections_mean(a: ActivityFixture) -> None:
    """609 and 1205 printed each graph's edges as arrows or plain lines, so spotting a "→" answered
    them (#214 C4). Now no edge is written out: the student decides from what each connection
    means, and one directed graph has every connection returned (two arrows are still directed)."""
    for text in [a.config["prompt"]] + [item["label"] for item in a.config["left"]]:
        assert not EDGE.search(text), text
        assert "→" not in text
    answers = [right_label(a, item["id"]) for item in a.config["left"]]
    assert sorted(set(answers)) == ["Directed", "Undirected"]
    for message in a.solution["feedback"].values():
        assert "how the edges are written" not in message
        assert message.startswith("Not quite.")
    assert "each other" in a.hints[2].body or "every pair" in a.hints[2].body


# --- Objective 5: tracing ---------------------------------------------------------------------------


def traces() -> list[ActivityFixture]:
    return [a for a in EVERY if a.kind == "trace"]


@pytest.mark.parametrize("a", traces(), ids=lambda a: str(a.id))
def test_the_trace_hints_are_the_engines_steps(a: ActivityFixture) -> None:
    steps = run_bfs(GraphScenarioOut(id=0, name="", **dict(a.config))).steps
    assert 6 <= len(a.config["vertices"]) <= 8  # Table 1: an unseen graph of 6 to 8 vertices
    order = ", ".join(s.visited_vertex for s in steps)
    queues = "; ".join("[" + ", ".join(s.queue) + "]" for s in steps)
    assert f"order {order}." in a.hints[-1].body
    assert f"Queues after each row: {queues}." in a.hints[-1].body
    first = steps[0]
    assert (
        f"{first.visited_vertex} leaves; the queue becomes {', '.join(first.queue)}."
        in a.hints[2].body
    )
    assert f"from {a.config['start_vertex']}" in a.title
    # The engine's words: found when a vertex joins the queue, visited when it leaves.
    assert "visited when it joins" not in " ".join(h.body for h in a.hints)


def test_the_queue_practice_answer_is_what_bfs_does() -> None:
    practice = next(a for a in PRACTICE if a.objective_id == 5)
    queue, found = ["C", "D"], {"A", "B", "C", "D"}
    current = queue.pop(0)
    for n in sorted(["A", "D", "E"]):
        if n not in found:
            found.add(n)
            queue.append(n)
    assert current == "C"
    correct = next(
        o["label"] for o in practice.config["options"] if o["id"] == practice.solution["correct"]
    )
    assert correct == ", ".join(queue)


# --- Objective 6: building BFS ---------------------------------------------------------------------


def test_the_reference_bfs_passes_every_hidden_test() -> None:
    parsons = next(a for a in CHECK if a.kind == "parsons")
    assert passes_hidden(lines_text(parsons, first_order(parsons)))


def conventional(order: list[int], text: dict[int, str]) -> bool:
    """The import comes first, and the order gets the vertex straight after it leaves the queue:
    the two orders that run but are marked wrong on purpose (see test_module_4.py)."""
    lines = [text[i].strip() for i in order]
    after_dequeue = lines[next(n for n, t in enumerate(lines) if ".popleft()" in t) + 1]
    return lines[0].startswith("from ") and after_dequeue.startswith("order.append(")


ORDERED = [a for a in EVERY if a.kind in ("parsons", "fix_the_bug")]


@pytest.mark.parametrize("a", ORDERED, ids=lambda a: str(a.id))
def test_an_ordered_item_accepts_exactly_the_working_orders(a: ActivityFixture) -> None:
    """Every order of the answer's lines Python can run is tried on the hidden tests: each the
    checker accepts passes, and each that passes is accepted, but for the two conventions above
    (FR-5.4, FR-5.5, #145). Objectives 6 and 7 need every part right, so a working order marked
    wrong would decide the result. Distractors and corrections are covered by the tests below."""
    every = {x["id"]: x["text"] for x in a.config["lines"] + a.config.get("corrections", [])}
    text = {i: every[i] for i in first_order(a)}
    working, accepted = [], []
    for order in runnable_orders(text):
        if passes_hidden(lines_text(a, order)):
            working.append(order)
        if check_activity(a.kind, a.config, a.solution, {"order": order}).correct:
            accepted.append(order)
    assert accepted == [order for order in working if conventional(order, text)]
    assert len(accepted) == 12
    assert len(working) == 48
    shown = [x["id"] for x in a.config["lines"]]
    assert not check_activity(a.kind, a.config, a.solution, {"order": shown}).correct


# A correction that is harmless once the real bug is fixed: the program runs, but the line it
# replaces was never faulty, so fix the bug marks it "did not need a correction" (flagged on #145).
# None is left: 1703's correction 22 (`and n != v`) is retired and replaced by one that breaks BFS
# (#147).
HARMLESS: dict[int, list[tuple[int, ...]]] = {}


@pytest.mark.parametrize(
    "a", [a for a in EVERY if a.kind == "fix_the_bug"], ids=lambda a: str(a.id)
)
def test_no_other_correction_makes_a_working_program(a: ActivityFixture) -> None:
    """Replacing one or two lines of the fixed program with any other line or correction of the
    same indentation never runs correctly, except the listed harmless ones."""
    every = {x["id"]: x["text"] for x in a.config["lines"] + a.config["corrections"]}
    fixed = first_order(a)

    def indent(i: int) -> int:
        return len(every[i]) - len(every[i].lstrip())

    working = set()
    for count in (1, 2):
        for slots in combinations(range(len(fixed)), count):
            options = [
                [c for c in every if c not in fixed and indent(c) == indent(fixed[s])]
                for s in slots
            ]
            for pick in product(*options):
                order = list(fixed)
                for slot, line in zip(slots, pick, strict=True):
                    order[slot] = line
                if passes_hidden(lines_text(a, order)):
                    working.add(tuple(order))
    assert sorted(working) == HARMLESS.get(a.id, [])


def test_each_parsons_distractor_breaks_bfs() -> None:
    a = next(a for a in CHECK if a.kind == "parsons")
    order = first_order(a)
    by_id = {x["id"]: x["text"] for x in a.config["lines"]}
    distractors = [x for x in a.config["lines"] if x["id"] not in order]
    assert len(distractors) == 4
    for d in distractors:
        # Put it in place of the line it imitates (the same start), as a student would.
        key = d["text"].split()[0]
        swapped = [d["id"] if by_id[i].split()[0] == key else i for i in order]
        assert swapped != order
        assert not passes_hidden(lines_text(a, swapped)), d["text"]


FILL_INS = [a for a in EVERY if a.kind == "fill_in"]


@pytest.mark.parametrize("a", FILL_INS, ids=lambda a: str(a.id))
def test_the_fill_in_answers_make_working_bfs(a: ActivityFixture) -> None:
    assert sorted(int(n) for n in BLANK.findall(a.config["code"])) == a.config["blanks"]
    assert passes_hidden(filled(a))


@pytest.mark.parametrize(
    ("a", "blank", "token"),
    [
        (a, str(blank), token)
        for a in FILL_INS
        for blank, messages in a.solution["feedback"].items()
        for token in messages
    ],
    ids=lambda x: str(getattr(x, "id", x)),
)
def test_each_wrong_token_really_breaks_bfs(a: ActivityFixture, blank: str, token: str) -> None:
    assert not passes_hidden(filled(a, **{blank: token}))


# --- Objective 7: fixing and testing ----------------------------------------------------------------

FIXES = [a for a in EVERY if a.kind == "fix_the_bug"]
CHOICES = [a for a in EVERY if a.kind == "choose_tests"]


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_the_faulty_program_fails_and_the_fixed_one_passes(a: ActivityFixture) -> None:
    original = [x["id"] for x in a.config["lines"]]
    assert not passes_hidden(lines_text(a, original))
    assert passes_hidden(lines_text(a, first_order(a)))


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_each_wrong_correction_leaves_bfs_broken(a: ActivityFixture) -> None:
    order = first_order(a)
    used = [c for c in a.config["corrections"] if c["id"] in order]
    unused = [c for c in a.config["corrections"] if c["id"] not in order]
    assert unused, "a correction to choose from, not only the right one"
    for wrong in unused:
        for right in used:
            swapped = [wrong["id"] if i == right["id"] else i for i in order]
            assert not passes_hidden(lines_text(a, swapped)), (wrong["text"], right["text"])


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_a_wrong_correction_in_place_of_any_one_line_breaks_bfs(a: ActivityFixture) -> None:
    """A wrong correction is a real mistake: put in place of any one line of the fixed program, BFS
    fails a hidden test (1703's "and n != v" passed them all, #147). It is not true of every
    arrangement: a wrong line added as a dead assignment, or with other lines moved, can still run
    like BFS. The grader marks those wrong because they aren't the fix the item asks for."""
    order = [i for x in a.solution["order"] for i in (x if isinstance(x, list) else [x])]
    for wrong in (c for c in a.config["corrections"] if c["id"] not in order):
        for place in range(len(order)):
            changed = [*order[:place], wrong["id"], *order[place + 1 :]]
            assert not passes_hidden(lines_text(a, changed)), (wrong["text"], place)


@pytest.mark.parametrize("a", CHOICES, ids=lambda a: str(a.id))
def test_the_exposing_tests_are_exactly_the_ones_the_faulty_version_fails(
    a: ActivityFixture,
) -> None:
    fails = []
    for t in a.config["tests"]:
        edges = [(e["source"], e["target"]) for e in t["edges"]]
        reference = run_bfs(scenario(t["directed"], t["vertices"], edges, t["start_vertex"])).order
        assert t["expected"] == reference  # the correct BFS passes every test
        got = run_bfs_code(a.config["code"], t["directed"], t["vertices"], edges, t["start_vertex"])
        if got != t["expected"]:
            fails.append(t["id"])
    assert sorted(fails) == sorted(a.solution["exposing"])
    assert 4 <= len(a.config["tests"]) <= 6  # FR-5.5


def test_the_tests_include_a_disconnected_graph_and_a_graph_with_a_cycle() -> None:
    """Objective 7: "including a disconnected graph or a graph containing a cycle"; in each set,
    one bug is exposed by a cycle and one by a disconnected graph."""
    for items in (
        [a for a in CHECK if a.kind == "choose_tests"],
        [a for a in FRESH[7] if a.kind == "choose_tests"],
    ):
        exposed = {e for a in items for e in a.solution["exposing"]}
        assert "cycle" in exposed
        assert "two-islands" in exposed


def test_the_recall_item_names_two_routes_not_a_cycle() -> None:
    """625 said "a graph containing a cycle" shows the visited-too-late bug, which set the student
    up to get 623 wrong: there a directed cycle passes and a fork-join with no cycle fails (round 2
    review of #215, content 1)."""
    recall = ACTIVITIES[625]
    key = next(
        o["label"] for o in recall.config["options"] if o["id"] == recall.solution["correct"]
    )
    assert "two routes" in key
    assert "cycle" not in key
    verdicts = ACTIVITIES[623]
    fails = set(verdicts.solution["exposing"])
    cyclic = {t["id"] for t in verdicts.config["tests"] if t["id"] in ("cycle", "back-to-start")}
    assert "fork-join" in fails  # no cycle, two routes to D
    assert cyclic - fails == {"back-to-start"}  # a cycle, one route to each vertex


def test_every_hidden_test_graph_runs_on_the_engine() -> None:
    for directed, vertices, edges, start in HIDDEN.values():
        assert run_bfs(scenario(directed, vertices, edges, start)).order


def test_objective_8_items_ask_for_the_fewest_edges_not_the_quickest() -> None:
    """626 asked for the "quickest" trip, which module 3 (worked example 392) teaches BFS can't
    find when edges take different times (#214 C10)."""
    for a in (a for a in EVERY if a.objective_id == 8):
        assert not re.search(r"quickest|fastest|shortest time", str(a.config.get("prompt", "")))


def test_objective_4_hint_3_is_a_partial_solution_for_its_own_item() -> None:
    """All eight objective 4 items had the same hints 1 to 3, and hint 3 repeated hint 2 as a
    question, yet opening it marks the answer "met with support" (#214 C12)."""
    items = [a for a in EVERY if a.objective_id == 4 and a.purpose == "mastery"]
    assert len(items) == 8
    for level in (2, 3):
        bodies = [a.hints[level - 1].body for a in items]
        assert len(set(bodies)) == len(bodies), level
    for a in items:
        assert a.hints[2].body != a.hints[1].body
        assert "Does this problem ask for one of those two jobs?" not in a.hints[2].body


def test_a_review_fill_in_is_as_hard_as_the_module_6_one() -> None:
    """1602 blanked parts with two tokens each that fit, the next line giving one away, so a
    student met objective 6 again without the skill 620 found missing (#214 C13). Now each blank
    has at least two wrong tokens of its own kind, each with feedback, as in 620."""
    for a in (a for a in FRESH[6] + CHECK if a.kind == "fill_in"):
        for blank in a.config["blanks"]:
            assert len(a.solution["feedback"][str(blank)]) >= 2, (a.id, blank)


def test_the_review_fill_in_blanks_other_parts_than_620() -> None:
    """1602 was 620 with renamed variables: the same four blanks, the same tokens (round 2 review
    of #215). Now it blanks other parts of BFS: building the queue, whose neighbours, which vertex
    is marked found, and where it joins."""
    names = {"discovered": "visited", "lineup": "queue", "here": "v", "nbr": "n"}

    def blanked(a: ActivityFixture) -> set[str]:
        lines = {line.strip() for line in a.config["code"].splitlines() if BLANK.search(line)}
        for old, new in names.items():
            lines = {re.sub(rf"\b{old}\b", new, line) for line in lines}
        return {BLANK.sub("__", line) for line in lines}

    def answers(a: ActivityFixture) -> set[str]:
        found = set(a.solution["answers"].values())
        for old, new in names.items():
            found = {re.sub(rf"\b{old}\b", new, x) for x in found}
        return found

    assert not blanked(ACTIVITIES[1602]) & blanked(ACTIVITIES[620])
    assert not answers(ACTIVITIES[1602]) & answers(ACTIVITIES[620])


@pytest.mark.parametrize("a", LABELLING, ids=lambda a: str(a.id))
def test_the_places_letters_are_not_their_initials(a: ActivityFixture) -> None:
    """The kitchen was K and the river corner R in 607 and 1204, so the letter lookup was a free
    lexical link (#214 C15); 606 and 1203 already used other letters."""
    named = NAMED.findall(a.config["prompt"])
    initials = [
        (name, letter)
        for name, letter in named
        if letter in {w[0].upper() for w in name.removeprefix("the ").split()}
    ]
    assert len(initials) <= 1, initials  # one by chance (606's shed tap is S), not a pattern
