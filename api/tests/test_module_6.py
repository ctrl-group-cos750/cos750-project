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
from types import FrameType
from typing import Any

import pytest

from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture, FixtureFile, ReviewPathFixture, read_fixtures
from app.services.bfs import run_bfs
from app.services.mastery import MASTERY_MODULE, Rule

CONTENT: FixtureFile = read_fixtures()
ACTIVITIES = {a.id: a for a in CONTENT.activities}
MODULE = next(m for m in CONTENT.modules if m.id == MASTERY_MODULE)
OBJECTIVES = {o.id: o for o in CONTENT.objectives}
PATHS: dict[int, ReviewPathFixture] = {r.objective_id: r for r in CONTENT.review_paths}
CHECK = [ACTIVITIES[s.activity_id] for s in MODULE.segments if s.activity_id is not None]
FRESH = {
    o: [ACTIVITIES[s.activity_id] for s in p.segments if s.activity_id is not None][1:]
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
            return len(a.solution["order"])
        case "fill_in":
            return len(a.config["blanks"])
        case "choose_tests":
            return len(a.config["tests"])
    raise AssertionError(a.kind)


def items_of(where: str, objective: int) -> list[ActivityFixture]:
    if where == "module 6":
        return [a for a in CHECK if a.objective_id == objective]
    return FRESH[objective]


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
    assert [a.id for a in CHECK] == list(range(601, 601 + len(CHECK)))
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
        )

    check = {seen(a) for a in CHECK}
    assert not check & {seen(a) for items in FRESH.values() for a in items}


def test_the_right_option_is_not_always_in_the_same_place() -> None:
    places = Counter(
        [o["id"] for o in a.config["options"]].index(a.solution["correct"])
        for a in EVERY
        if a.kind == "multiple_choice"
    )
    assert len(places) == 3
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
            faulty = {x["id"] for x in a.config["lines"]} - set(a.solution["order"])
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
    assert len(LABELLING) == 6
    assert len(CLASSIFYING) == 2


class Drawn:
    """The graph a labelling prompt describes in words, and the questions a marker asks of it."""

    def __init__(self, prompt: str) -> None:
        self.edges = [(u, arrow, v) for u, arrow, v in EDGE.findall(prompt)]
        self.vertices = {x for u, _, v in self.edges for x in (u, v)}

    def touching(self, x: str) -> set[tuple[str, str, str]]:
        return {e for e in self.edges if x in (e[0], e[2])}

    def neighbours(self, x: str) -> set[str]:
        return {v if u == x else u for u, _, v in self.touching(x)}

    def leaving(self, x: str) -> set[tuple[str, str, str]]:
        return {e for e in self.edges if e[0] == x}

    def arriving(self, x: str) -> set[tuple[str, str, str]]:
        return {e for e in self.edges if e[2] == x}

    def sinks(self) -> set[str]:
        return {x for x in self.vertices if not self.leaving(x) and self.arriving(x)}


def only(found: set[Any]) -> Any:
    assert len(found) == 1, found  # the marker picks out exactly one part
    return next(iter(found))


def vertex(x: str) -> str:
    return f"Vertex {x}"


def edge(e: tuple[str, str, str]) -> str:
    u, arrow, v = e
    return f"Edge {u} → {v}" if arrow == "→" else f"Edge {u}{DASH}{v}"


# What each marker describes, worked out from the edges the prompt lists. A marker used to name
# its own answer ("Marker 1: tap Q"), so the item only tested that a tap is a vertex (#147).
MARKERS: dict[int, dict[str, Any]] = {
    606: {  # the tap joined to P; the only hose at P; the only hose at S
        "1": lambda g: vertex(only(g.neighbours("P"))),
        "2": lambda g: edge(only(g.touching("P"))),
        "3": lambda g: edge(only(g.touching("S"))),
    },
    607: {  # K's doorway not to L; the room other than K joined to L and M; N's doorway not to M
        "1": lambda g: edge(only({e for e in g.touching("K") if "L" not in e})),
        "2": lambda g: vertex(only((g.neighbours("L") & g.neighbours("M")) - {"K"})),
        "3": lambda g: edge(only({e for e in g.touching("N") if "M" not in e})),
    },
    608: {  # the road leaving X; the stop with no way out; the road arriving at Z
        "1": lambda g: edge(only(g.leaving("X"))),
        "2": lambda g: vertex(only(g.sinks())),
        "3": lambda g: edge(only(g.arriving("Z"))),
    },
    1202: {  # A's road to the stop that also reaches D; the stop whose only road is to A; D's road
        "1": lambda g: edge(only({e for e in g.touching("A") if "D" in g.neighbours(e[2])})),
        "2": lambda g: vertex(only({x for x in g.vertices if g.neighbours(x) == {"A"}})),
        "3": lambda g: edge(only(g.touching("D"))),
    },
    1203: {  # the computer joined to F and G; the cable not at E; G's cable not to F
        "1": lambda g: vertex(only({x for x in g.vertices if {"F", "G"} <= g.neighbours(x)})),
        "2": lambda g: edge(only({e for e in g.edges if "E" not in e})),
        "3": lambda g: edge(only({e for e in g.touching("G") if "F" not in e})),
    },
    1204: {  # the street leaving S; the corner with no way out; the street arriving at S
        "1": lambda g: edge(only(g.leaving("S"))),
        "2": lambda g: vertex(only(g.sinks())),
        "3": lambda g: edge(only(g.arriving("S"))),
    },
}


def same_part(a: str, b: str) -> bool:
    """An undirected edge is the same edge whichever end is named first."""
    if DASH in a and DASH in b:
        return set(a.removeprefix("Edge ").split(DASH)) == set(b.removeprefix("Edge ").split(DASH))
    return a == b


@pytest.mark.parametrize("a", LABELLING, ids=lambda a: str(a.id))
def test_each_marker_picks_out_the_part_its_answer_names(a: ActivityFixture) -> None:
    drawn = Drawn(a.config["prompt"])
    assert {arrow for _, arrow, _ in drawn.edges} in ({DASH}, {"→"})
    markers = MARKERS[a.id]
    assert sorted(markers) == sorted(item["id"] for item in a.config["left"])
    for item in a.config["left"]:
        answer = right_label(a, item["id"])
        assert same_part(answer, markers[item["id"]](drawn)), item["label"]
        # The marker no longer gives its answer away: it doesn't spell out the part's name.
        named = set(re.findall(r"[A-Z]", answer.split(" ", 1)[1]))
        assert not named <= set(re.findall(r"\b[A-Z]\b", item["label"].split(": ", 1)[1]))
    # The answer hint says the same.
    for item in a.config["left"]:
        assert f"{item['id']} = {right_label(a, item['id'])}" in a.hints[-1].body


@pytest.mark.parametrize("a", CLASSIFYING, ids=lambda a: str(a.id))
def test_each_graph_is_classified_by_how_its_edges_are_written(a: ActivityFixture) -> None:
    for item in a.config["left"]:
        arrows = {arrow for _, arrow, _ in EDGE.findall(item["label"])}
        want = "Directed" if arrows == {"→"} else "Undirected"
        assert arrows in ({"→"}, {DASH})
        assert right_label(a, item["id"]) == want, item["id"]


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
    assert passes_hidden(lines_text(parsons, parsons.solution["order"]))


def test_each_parsons_distractor_breaks_bfs() -> None:
    a = next(a for a in CHECK if a.kind == "parsons")
    order = a.solution["order"]
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
    assert passes_hidden(lines_text(a, a.solution["order"]))


@pytest.mark.parametrize("a", FIXES, ids=lambda a: str(a.id))
def test_each_wrong_correction_leaves_bfs_broken(a: ActivityFixture) -> None:
    order = a.solution["order"]
    used = [c for c in a.config["corrections"] if c["id"] in order]
    unused = [c for c in a.config["corrections"] if c["id"] not in order]
    assert unused, "a correction to choose from, not only the right one"
    for wrong in unused:
        for right in used:
            swapped = [wrong["id"] if i == right["id"] else i for i in order]
            assert not passes_hidden(lines_text(a, swapped)), (wrong["text"], right["text"])


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


def test_every_hidden_test_graph_runs_on_the_engine() -> None:
    for directed, vertices, edges, start in HIDDEN.values():
        assert run_bfs(scenario(directed, vertices, edges, start)).order
