"""Support groups for modules 1 to 4 (#173): a short worked example, then one or two fresh
questions on the same objective, for a student who is struggling on it (#172 decides who).

These tests read the fixture JSON directly, so they check the content whatever the mechanism
that shows it does. They check what an item writer and a reviewer would check by hand:

- one group per objective a module practises, in the module's 90s, straight after that
  objective's last practice segment, with the worked example first (ID document §5.2: example,
  then problem; Atkinson et al. 2000);
- each worked example ends with a self-explanation prompt (06-literature recommendation 6);
- every question has the four hint levels (§7.3) and three-part feedback on every wrong answer
  (§7.4: result, reason, next step), and every graph is described in text (§6.2, WCAG 1.1.1);
- every BFS order and trace is the engine's, and every code answer is checked by running it;
- no surface cue gives an answer away (#147's rules), and nothing repeats the mastery check
  (module 6) or the review paths: no shared graph, no restated situation.
"""

import difflib
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from parsons_orders import runnable_orders

from app.schemas.graphs import GraphEdge, GraphScenarioOut
from app.seed import ActivityFixture
from app.services.bfs import run_bfs
from app.services.checking import check_activity

SEED = Path(__file__).parents[1] / "app" / "seed"
DASH = "\N{EN DASH}"
ARROW = "→"
EDGE = re.compile(rf"\b([A-Z]) ?({DASH}|{ARROW}) ?([A-Z])\b")


def fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SEED / name).read_text(encoding="utf-8"))
    return data


MODULES = {n: fixture(f"module-{n}.json") for n in range(1, 5)}
SEGMENTS = {n: d["modules"][0]["segments"] for n, d in MODULES.items()}
ACTIVITIES = {a["id"]: a for d in MODULES.values() for a in d["activities"]}
MASTERY_FILES = [fixture("module-6.json"), fixture("review.json")]
CHECK_ITEMS = [a for d in MASTERY_FILES for a in d["activities"]]
REVIEW_SEGMENTS = [
    s for d in MASTERY_FILES for r in d.get("review_paths", []) for s in r["segments"]
]

# The groups, as the card asks: (module, objective) -> the segment ids, worked example first.
GROUPS = {
    (1, 1): [190, 191],
    (1, 2): [192, 193, 194],
    (1, 3): [195, 196],
    (2, 2): [290, 291],
    (2, 6): [292, 293, 294],
    (3, 5): [390, 391],
    (3, 4): [392, 393],
    (3, 8): [397, 398],
    (4, 6): [490, 491, 492],
}


def support_segments(module: int) -> list[dict[str, Any]]:
    return [s for s in SEGMENTS[module] if s.get("support_for") is not None]


SUPPORT_ACTIVITIES = [
    ACTIVITIES[s["activity_id"]]
    for n in MODULES
    for s in support_segments(n)
    if s.get("activity_id")
]
WORKED = [s for n in MODULES for s in support_segments(n) if s["kind"] == "text"]


def activity(activity_id: int) -> dict[str, Any]:
    found: dict[str, Any] = ACTIVITIES[activity_id]
    return found


def right_label(a: dict[str, Any]) -> str:
    return str(
        next(o["label"] for o in a["config"]["options"] if o["id"] == a["solution"]["correct"])
    )


def scenario(directed: bool, vertices: list[str], edges: list[tuple[str, str]], start: str) -> Any:
    return GraphScenarioOut(
        id=0,
        name="",
        directed=directed,
        vertices=vertices,
        edges=[GraphEdge(source=u, target=v) for u, v in edges],
        start_vertex=start,
    )


# --- Where the groups are ---------------------------------------------------------------------


def base_objective(segment: dict[str, Any]) -> int | None:
    """The objective a base (everyone's) segment practises, through its activity or skip check."""
    ref = segment.get("activity_id") or segment.get("skip_check_activity_id")
    if ref is None or segment.get("support_for") is not None:
        return None
    a = ACTIVITIES[ref]
    return a["objective_id"] if a["purpose"] == "practice" else None


def test_every_objective_a_module_practises_has_one_group() -> None:
    for n in MODULES:
        practised = {base_objective(s) for s in SEGMENTS[n]} - {None}
        groups = {o for (m, o) in GROUPS if m == n}
        assert groups == practised, n
        assert {s["support_for"] for s in support_segments(n)} == practised


@pytest.mark.parametrize(("module", "objective"), sorted(GROUPS))
def test_a_group_is_a_worked_example_then_one_or_two_questions(module: int, objective: int) -> None:
    ids = [s["id"] for s in SEGMENTS[module]]
    start = ids.index(GROUPS[(module, objective)][0])
    group = SEGMENTS[module][start : start + len(GROUPS[(module, objective)])]
    assert [s["id"] for s in group] == GROUPS[(module, objective)]
    assert all(s["support_for"] == objective for s in group)
    assert group[0]["kind"] == "text"
    assert all(s["kind"] == "activity" for s in group[1:])
    assert 1 <= len(group) - 1 <= 2
    # After every base practice segment on the objective except the closing task, so the trigger
    # (#172) has evidence; before the closing task, which then checks the skill after the help.
    at = {s["id"]: i for i, s in enumerate(SEGMENTS[module])}
    for s in SEGMENTS[module]:
        if base_objective(s) == objective and not closing(s):
            assert at[s["id"]] < start, (module, objective, s["id"])
    assert start < at[next(s["id"] for s in SEGMENTS[module] if closing(s))]


def closing(segment: dict[str, Any]) -> bool:
    return str(segment["title"]).startswith("Closing task")


# Each module's segments in order after this card, support in brackets: the positions #172's
# migration of saved progress must handle (a saved position is an index into this list).
ORDER = {
    1: [
        101,
        102,
        103,
        104,
        [190, 191],
        105,
        170,
        106,
        107,
        108,
        109,
        [192, 193, 194],
        [195, 196],
        110,
    ],
    2: [203, 204, 270, 205, [290, 291], 206, 207, 271, 208, [292, 293, 294], 209],
    3: [313, 314, [392, 393], 315, 316, 317, 370, 318, [390, 391], 320, 321, [397, 398], 319],
    4: [403, 404, 470, 405, 406, 471, 472, 473, 407, [490, 491, 492], 408],
}


def test_the_segments_are_in_the_order_reported_for_saved_progress() -> None:
    for n, order in ORDER.items():
        flat = [i for x in order for i in (x if isinstance(x, list) else [x])]
        assert [s["id"] for s in SEGMENTS[n]] == flat, n
        assert [s["id"] for s in support_segments(n)] == [
            i for x in order if isinstance(x, list) for i in x
        ]


def test_the_ids_are_the_modules_90s_and_used_once() -> None:
    for n in MODULES:
        for s in support_segments(n):
            assert n * 100 + 90 <= s["id"] <= n * 100 + 99
            if s.get("activity_id"):
                assert n * 100 + 90 <= s["activity_id"] <= n * 100 + 99
    seg_ids = [
        s["id"]
        for d in [*MODULES.values(), *MASTERY_FILES]
        for m in d.get("modules", [])
        for s in m["segments"]
    ]
    seg_ids += [s["id"] for s in REVIEW_SEGMENTS]
    assert len(seg_ids) == len(set(seg_ids))


def test_support_questions_are_practice_on_their_objective() -> None:
    for n in MODULES:
        for s in support_segments(n):
            if s.get("activity_id"):
                a = activity(s["activity_id"])
                assert (a["purpose"], a["objective_id"], a["module_id"]) == (
                    "practice",
                    s["support_for"],
                    n,
                )
    # Nothing outside the support segments shows them, and nothing in module 6 or a review path
    # is support.
    shown = [
        s.get("activity_id") for n in MODULES for s in SEGMENTS[n] if s.get("support_for") is None
    ]
    assert not {a["id"] for a in SUPPORT_ACTIVITIES} & set(shown)
    assert all("support_for" not in s for s in REVIEW_SEGMENTS)
    assert all("support_for" not in s for s in MASTERY_FILES[0]["modules"][0]["segments"])


def test_the_existing_segments_keep_their_order() -> None:
    """The support segments are inserted; everyone's segments are as on staging, in order, with
    #150's segments (170, 270, 271, 370, 470-473) and objective 8's worked example and practice
    (320, 321; #70) inserted among them."""
    base = {
        1: [101, 102, 103, 104, 105, 170, 106, 107, 108, 109, 110],
        2: [203, 204, 270, 205, 206, 207, 271, 208, 209],
        3: [313, 314, 315, 316, 317, 370, 318, 320, 321, 319],
        4: [403, 404, 470, 405, 406, 471, 472, 473, 407, 408],
    }
    for n, ids in base.items():
        assert [s["id"] for s in SEGMENTS[n] if s.get("support_for") is None] == ids


# --- Worked examples --------------------------------------------------------------------------


@pytest.mark.parametrize("segment", WORKED, ids=lambda s: str(s["id"]))
def test_a_worked_example_ends_with_a_self_explanation_prompt(segment: dict[str, Any]) -> None:
    last = segment["body"].split("\n\n")[-1]
    assert last.startswith("**Explain it to yourself before you go on:**")
    assert last.endswith("?")


@pytest.mark.parametrize("segment", WORKED, ids=lambda s: str(s["id"]))
def test_a_worked_example_is_short(segment: dict[str, Any]) -> None:
    """About a minute's reading: the course is already over its time budget (the note under the
    ID document's Table 4)."""
    assert len(re.findall(r"\w+", segment["body"])) <= 280


# --- Hints and feedback -----------------------------------------------------------------------


@pytest.mark.parametrize("a", SUPPORT_ACTIVITIES, ids=lambda a: str(a["id"]))
def test_a_support_question_is_valid_content(a: dict[str, Any]) -> None:
    ActivityFixture.model_validate(a)  # the kind's schema, a reachable solution


@pytest.mark.parametrize("a", SUPPORT_ACTIVITIES, ids=lambda a: str(a["id"]))
def test_four_hint_levels_and_the_last_gives_the_answer(a: dict[str, Any]) -> None:
    assert [h["level"] for h in a["hints"]] == [1, 2, 3, 4]
    assert a["hints"][-1]["body"].startswith("Answer:")
    assert all(h["body"].strip() for h in a["hints"])


def three_parts(message: str) -> bool:
    """Result ("Not quite."), a reason and a next step: at least three sentences."""
    sentences = [s for s in re.split(r"(?<=[.?!])\s+", message) if s]
    return message.startswith("Not quite.") and len(sentences) >= 3


@pytest.mark.parametrize("a", SUPPORT_ACTIVITIES, ids=lambda a: str(a["id"]))
def test_every_wrong_answer_has_three_part_feedback(a: dict[str, Any]) -> None:
    config, solution = a["config"], a["solution"]
    match a["kind"]:
        case "multiple_choice":
            wrong = {o["id"] for o in config["options"]} - {solution["correct"]}
            assert set(solution["feedback"]) == wrong
            messages = list(solution["feedback"].values())
        case "matching":
            assert set(solution["feedback"]) == {item["id"] for item in config["left"]}
            messages = list(solution["feedback"].values())
        case "fill_in":
            # Every blank has its likely mistakes explained; others get the checker's message.
            assert set(solution["feedback"]) == {str(b) for b in config["blanks"]}
            messages = [m for blank in solution["feedback"].values() for m in blank.values()]
        case _:
            # Trace and Parsons: the checker writes the message for each wrong row or line.
            assert a["kind"] in ("trace", "parsons")
            messages = []
    for message in messages:
        assert three_parts(message), message


def test_every_wrong_answer_is_marked_wrong_and_the_right_one_right() -> None:
    for a in SUPPORT_ACTIVITIES:
        config, solution = a["config"], a["solution"]
        if a["kind"] == "multiple_choice":
            for o in config["options"]:
                result = check_activity(a["kind"], config, solution, {"selected": o["id"]})
                assert result.correct == (o["id"] == solution["correct"]), (a["id"], o["id"])
        if a["kind"] == "matching":
            result = check_activity(a["kind"], config, solution, {"pairs": solution["pairs"]})
            assert result.correct, a["id"]
            for left in solution["feedback"]:
                other = next(r["id"] for r in config["right"] if r["id"] != solution["pairs"][left])
                pairs = solution["pairs"] | {left: other}
                result = check_activity(a["kind"], config, solution, {"pairs": pairs})
                assert not result.correct
                assert solution["feedback"][left] in [p.message for p in result.parts], a["id"]
        if a["kind"] == "fill_in":
            answers = {int(k): v for k, v in solution["answers"].items()}
            assert check_activity(a["kind"], config, solution, {"answers": answers}).correct
            for blank, tokens in solution["feedback"].items():
                for token, message in tokens.items():
                    result = check_activity(
                        a["kind"], config, solution, {"answers": answers | {int(blank): token}}
                    )
                    assert [p.message for p in result.parts if not p.correct] == [message]


# --- Graphs: described in text, and every answer the engine's -----------------------------------


def edges_in(text: str) -> list[tuple[str, str, bool]]:
    return [(u, v, arrow == ARROW) for u, arrow, v in EDGE.findall(text)]


def described(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """The vertices and edges a worked example's text description lists."""
    match = re.search(r"vertices ([A-Z](?:, [A-Z])*,? and [A-Z]),? and edges ([^.]+)\.", text)
    assert match, text
    vertices = re.findall(r"[A-Z]", match.group(1))
    return vertices, [(u, v) for u, v, _ in edges_in(match.group(2))]


def test_the_trace_worked_example_rows_are_the_engines_steps() -> None:
    body = next(s for s in WORKED if s["id"] == 390)["body"]
    vertices, edges = described(body)
    result = run_bfs(scenario(False, vertices, edges, "Q"))
    rows = re.findall(r"^\| (\d) \| (\w) \| ([\w, ()]+) \| ([\w, ]+) \| ([\w, ]+) \|$", body, re.M)
    assert len(rows) == len(result.steps) == len(vertices)
    for (n, current, queue, visited, order), step in zip(rows, result.steps, strict=True):
        assert current == step.visited_vertex, n
        assert (queue.split(", ") if queue != "(empty)" else []) == step.queue, n
        assert visited.split(", ") == step.visited, n
        assert order.split(", ") == step.order, n
    # What the text says about steps 3 and 4: only M joins, then only P.
    assert result.steps[2].discovered == ["M"]
    assert "R" in result.steps[1].queue  # R is already waiting when S leaves
    assert result.steps[3].discovered == ["P"]
    # The order is not alphabetical, so the example doesn't teach "BFS goes A to Z" (Tilanterä
    # et al. 2025, 06-literature §6).
    assert result.order != sorted(result.order)


def test_the_trace_questions_hints_are_the_engines_answer() -> None:
    trace = activity(390)
    result = run_bfs(GraphScenarioOut(id=0, name="", **trace["config"]))
    last = trace["hints"][-1]["body"]
    assert ", ".join(result.order) in last
    assert ", ".join("[" + ", ".join(s.queue) + "]" for s in result.steps) in last
    # Hint 3: the worked step, the vertex that is already waiting.
    assert result.steps[2].visited_vertex == "H"
    assert result.steps[2].discovered == []
    assert result.steps[1].queue == ["H", "E"]
    assert result.order != sorted(result.order)
    # Every vertex has an edge, so the edge list the trace shows describes the whole graph.
    touched = {e["source"] for e in trace["config"]["edges"]} | {
        e["target"] for e in trace["config"]["edges"]
    }
    assert touched == set(trace["config"]["vertices"])


def test_the_text_descriptions_list_the_graphs_vertices_and_edges() -> None:
    # Module 1: sports day (worked example) and the farm.
    we = next(s for s in WORKED if s["id"] == 192)["body"]
    assert {frozenset((u, v)) for u, v, d in edges_in(we.split("**Step 3")[0]) if not d} == {
        frozenset(e) for e in ("FH", "FP", "HT", "PT")
    }
    farm = activity(191)
    assert {frozenset((u, v)) for u, v, _ in edges_in(farm["config"]["prompt"])} == {
        frozenset(e) for e in ("BD", "BG", "DW", "GW")
    }
    labels = {r["id"]: r["label"] for r in farm["config"]["right"]}
    for left, right in farm["solution"]["pairs"].items():
        if right.startswith("e"):
            ((u, v, _),) = edges_in(labels[right])
            assert frozenset((u, v)) in {frozenset(e) for e in ("BD", "BG", "DW", "GW")}, left
    # Module 4: the prompt's description is the graph its add_edge calls build.
    prompt = activity(491)["config"]["prompt"]
    calls = re.findall(r'add_edge\("(\w)", "(\w)"\)', prompt)
    vertices, edges = described(prompt)
    assert edges == calls
    assert set(vertices) == {x for e in calls for x in e}


# --- Code: the Graph class (module 2) and BFS (module 4), run --------------------------------------


BLANK = re.compile(r"__(\d+)__")
CODE_BLOCK = re.compile(r"```python\n(.+?)\n```", re.S)


def filled(a: dict[str, Any]) -> str:
    answers = {str(k): v for k, v in a["solution"]["answers"].items()}
    return BLANK.sub(lambda m: answers[m.group(1)], a["config"]["code"])


def graph_class() -> Any:
    """The student's finished Graph class: module 2's last base code activity, filled in."""
    namespace: dict[str, Any] = {}
    exec(filled(activity(207)), namespace)  # noqa: S102 - our own fixture code
    return namespace["Graph"]


def code_lines(code: str) -> list[str]:
    lines = (line.split("  #")[0].rstrip() for line in code.splitlines())
    return [line for line in lines if line.strip() and not line.strip().startswith("#")]


def test_the_support_class_is_the_class_module_2_builds() -> None:
    assert code_lines(filled(activity(291))) == code_lines(filled(activity(207)))
    we = CODE_BLOCK.search(next(s for s in WORKED if s["id"] == 292)["body"])
    assert we
    assert code_lines(we.group(1)) == code_lines(filled(activity(207)))


def build(calls: list[str], directed: bool = False) -> dict[str, list[str]]:
    g = graph_class()(directed=directed)
    for call in calls:
        exec(f"g.{call}", {"g": g})  # noqa: S102 - our own calls
    adjacency: dict[str, list[str]] = g.adjacency
    return adjacency


def test_the_dictionaries_in_module_2s_support_are_what_the_class_builds() -> None:
    body = next(s for s in WORKED if s["id"] == 290)["body"]
    dicts = [json.loads(d) for d in re.findall(r"`(\{.+?\})`", body)]
    edges = ['add_edge("H", "J")', 'add_edge("H", "M")', 'add_edge("J", "K")']
    assert dicts == [build(edges), build(edges, directed=True)]
    run = next(s for s in WORKED if s["id"] == 292)["body"].split("**Running it.**")[1]
    shown = [json.loads(d) for d in re.findall(r"`(\{.+?\})`", run)]
    first, both = ['add_edge("P", "R")'], ['add_edge("P", "R")', 'add_edge("R", "T")']
    assert shown == [build(first), build(both), build(both, directed=True)]
    # The self-explanation question: without the if line, R would lose P.
    assert build(both)["R"] == ["P", "T"]
    # Graphs to dictionaries: each graph's answer is what the class builds from its edges.
    item = activity(290)
    labels = {r["id"]: json.loads(r["label"]) for r in item["config"]["right"]}
    for left in item["config"]["left"]:
        found = edges_in(left["label"])
        directed = any(d for _, _, d in found)
        g = build(
            [f'add_vertex("{v}")' for v in "STU"]
            + [f'add_edge("{u}", "{v}")' for u, v, _ in found],
            directed,
        )
        assert labels[item["solution"]["pairs"][left["id"]]] == g, left["id"]
        others = [k for k, v in labels.items() if v == g]
        assert others == [item["solution"]["pairs"][left["id"]]]  # one right dictionary each


def test_the_predict_the_list_answer_is_the_classs() -> None:
    item = activity(292)
    calls = re.findall(r"(add_\w+\([^)]*\))", item["config"]["prompt"])
    adjacency = build(calls)
    assert json.loads(right_label(item)) == adjacency["L"]
    wiped = graph_class()
    wiped.add_vertex = lambda self, v: self.adjacency.__setitem__(v, [])
    g = wiped()
    for call in calls:
        exec(f"g.{call}", {"g": g})  # noqa: S102
    assert json.loads(item["config"]["options"][0]["label"]) == g.adjacency["L"]  # the "if" mistake


def reference() -> str:
    """Module 4's worked example code: the BFS the module builds."""
    body = next(s for s in SEGMENTS[4] if s["kind"] == "worked_example")["body"]
    match = CODE_BLOCK.search(body)
    assert match
    return match.group(1)


def bfs_of(code: str) -> Any:
    namespace: dict[str, Any] = {}
    exec(code, namespace)  # noqa: S102 - our own fixture code
    return namespace["bfs"]


def test_the_four_jobs_example_is_module_4s_bfs() -> None:
    we = CODE_BLOCK.search(next(s for s in WORKED if s["id"] == 490)["body"])
    assert we
    assert code_lines(we.group(1)) == code_lines(reference())


RENAMED = {"visited": "seen", "v": "current", "n": "neighbour"}


def renamed(code: str) -> str:
    for old, new in RENAMED.items():
        code = re.sub(rf"\b{old}\b", new, code)
    return code


def hidden_tests() -> list[tuple[list[str], bool, str, list[str]]]:
    """Graphs, a start, and the engine's order: the module 4 design's tests and the support MC."""
    cases = [
        ("ABC", ["AB", "AC", "BC"], False, "A"),
        ("ABCDEFG", ["AC", "AE", "BC", "BG", "CF", "DE", "EF"], False, "A"),
        ("ABCDEFG", ["AC", "AE", "BC", "BG", "CF", "DE", "EF"], False, "D"),
        ("ABCD", ["AD", "AB", "AC"], False, "A"),
        ("ABCD", ["AB", "CD"], False, "A"),
        ("ADG", ["AD", "DG", "GA"], True, "A"),
        ("A", [], False, "A"),
        ("KLMNP", ["KN", "KL", "LM", "NM", "MP"], False, "K"),
    ]
    out = []
    for vertices, edges, directed, start in cases:
        order = run_bfs(
            scenario(directed, list(vertices), [(e[0], e[1]) for e in edges], start)
        ).order
        out.append(
            (
                [f'add_edge("{e[0]}", "{e[1]}")' for e in edges]
                + [f'add_vertex("{v}")' for v in vertices],
                directed,
                start,
                order,
            )
        )
    return out


def passes(code: str) -> bool:
    try:
        bfs = bfs_of(code)
        return all(
            bfs(_graph(calls, directed), start) == order
            for calls, directed, start, order in hidden_tests()
        )
    except Exception:
        return False


def _graph(calls: list[str], directed: bool) -> Any:
    g = graph_class()(directed=directed)
    for call in calls:
        exec(f"g.{call}", {"g": g})  # noqa: S102
    return g


def test_the_parsons_answer_is_module_4s_bfs_with_new_names() -> None:
    a = activity(490)
    text = {line["id"]: line["text"] for line in a["config"]["lines"]}
    order = [
        i for step in a["solution"]["order"] for i in (step if isinstance(step, list) else [step])
    ]
    assert sorted(text) == sorted(order)  # no distractors, as in 404: this is extra help
    assert [text[i] for i in order] == code_lines(renamed(reference()))
    assert passes("\n".join(text[i] for i in order))
    shown = [line["id"] for line in a["config"]["lines"]]
    assert not check_activity("parsons", a["config"], a["solution"], {"order": shown}).correct


def test_the_parsons_problem_accepts_exactly_the_orders_that_work() -> None:
    """As for 404: every runnable order that passes the tests is accepted, except the two the
    lessons rule out (the import after the function, order.append not straight after popleft)."""
    a = activity(490)
    text: dict[int, str] = {line["id"]: line["text"] for line in a["config"]["lines"]}
    working, accepted = [], []
    for order in runnable_orders(text):
        if passes("\n".join(text[i] for i in order)):
            working.append(order)
        if check_activity("parsons", a["config"], a["solution"], {"order": order}).correct:
            accepted.append(order)

    def conventional(order: list[int]) -> bool:
        lines = [text[i].strip() for i in order]
        after_dequeue = lines[next(n for n, t in enumerate(lines) if ".popleft()" in t) + 1]
        return lines[0].startswith("from ") and after_dequeue.startswith("order.append(")

    assert accepted == [o for o in working if conventional(o)]
    assert len(accepted) == 12


def test_the_bfs_question_is_the_engines_order_and_each_mistake_is_real() -> None:
    item = activity(491)
    calls = re.findall(r"(add_edge\([^)]*\))", item["config"]["prompt"])
    g = _graph(calls, False)
    order = bfs_of(reference())(g, "K")
    vertices, edges = described(item["config"]["prompt"])
    assert order == run_bfs(scenario(False, vertices, edges, "K")).order
    assert json.loads(right_label(item)) == order
    options = {o["id"]: json.loads(o["label"]) for o in item["config"]["options"]}
    unsorted = bfs_of(reference().replace("sorted(graph.adjacency[v])", "graph.adjacency[v]"))
    assert options["a"] == unsorted(g, "K")  # neighbours in the order their edges were added
    assert options["b"] == sorted(order)  # alphabetical, which here is also depth-first
    assert len(options["d"]) != len(set(options["d"]))  # a vertex visited twice


# --- No cue gives the answer away (#147's rules) -----------------------------------------------

MARKDOWN = re.compile(r"`|\*\*|^#|\[[^\]]*\]\(|^\s*[-*] ", re.M)
WRONG_WORDS = [
    "unvisited",
    "marked visited",
    "marked as visited",
    "mark it visited",
    "is visited when it joins",
    "is visited as it joins",
]


def plain_text(value: Any, key: str = "") -> Iterator[str]:
    """Every string a student sees as plain text (code and Parsons lines are code)."""
    if isinstance(value, str):
        if key not in ("code", "text"):
            yield value
    elif isinstance(value, dict):
        for k, item in value.items():
            yield from plain_text(item, k)
    elif isinstance(value, list):
        for item in value:
            yield from plain_text(item, key)


def shown(a: dict[str, Any]) -> Iterator[str]:
    yield from plain_text(a["config"])
    yield from plain_text(a["solution"].get("feedback", {}))
    yield from (h["body"] for h in a["hints"])


@pytest.mark.parametrize("a", SUPPORT_ACTIVITIES, ids=lambda a: str(a["id"]))
def test_plain_text_has_no_markdown_and_found_means_found(a: dict[str, Any]) -> None:
    for text in shown(a):
        assert not MARKDOWN.search(text), text
        assert "\n" not in text
        assert not any(w in text.lower() for w in WRONG_WORDS), text
    for s in WORKED:
        assert not any(w in s["body"].lower() for w in WRONG_WORDS)


def test_multiple_choice_keys_give_nothing_away() -> None:
    mc = [a for a in SUPPORT_ACTIVITIES if a["kind"] == "multiple_choice"]
    for a in mc:
        ids = [o["id"] for o in a["config"]["options"]]
        lengths = {o["id"]: len(o["label"]) for o in a["config"]["options"]}
        key = lengths.pop(a["solution"]["correct"])
        assert key <= max(lengths.values()), a["id"]  # never the longest
        assert ids.index(a["solution"]["correct"]) != 0, a["id"]
    assert len(
        {[o["id"] for o in a["config"]["options"]].index(a["solution"]["correct"]) for a in mc}
    ) == len(mc)


@pytest.mark.parametrize(
    "a", [a for a in SUPPORT_ACTIVITIES if a["kind"] == "matching"], ids=lambda a: str(a["id"])
)
def test_matching_answers_are_not_in_order_or_forced(a: dict[str, Any]) -> None:
    right = [r["id"] for r in a["config"]["right"]]
    places = [right.index(a["solution"]["pairs"][item["id"]]) for item in a["config"]["left"]]
    if len(right) > 2:
        assert places != list(range(len(places)))
    # The last pair can't be had by elimination: a spare answer, or one used twice.
    used = list(a["solution"]["pairs"].values())
    assert len(right) > len(a["config"]["left"]) or len(used) != len(set(used))


# --- Nothing from the mastery check or the review paths ------------------------------------------


def graph_key(directed: bool, edges: list[tuple[str, str]]) -> frozenset[Any]:
    return frozenset((u, v) if directed else frozenset((u, v)) for u, v in edges)


def graphs_of(a: dict[str, Any]) -> list[frozenset[Any]]:
    """Every graph an item shows: a trace or test case's own, or one written out in a text."""
    c = a["config"]
    found = []
    if a["kind"] == "trace":
        found.append(graph_key(c["directed"], [(e["source"], e["target"]) for e in c["edges"]]))
    for t in c.get("tests", []):
        found.append(graph_key(t["directed"], [(e["source"], e["target"]) for e in t["edges"]]))
    for text in shown(a):
        if len(edges := edges_in(text)) >= 2:
            found.append(graph_key(any(d for *_, d in edges), [(u, v) for u, v, _ in edges]))
    return found


def support_graphs() -> list[frozenset[Any]]:
    found = [g for a in SUPPORT_ACTIVITIES for g in graphs_of(a)]
    for s in WORKED:
        for paragraph in s["body"].split("\n\n"):
            if len(edges := edges_in(paragraph)) >= 2:
                found.append(graph_key(any(d for *_, d in edges), [(u, v) for u, v, _ in edges]))
    return found


def test_no_support_graph_is_a_mastery_review_or_base_graph() -> None:
    support_ids = {a["id"] for a in SUPPORT_ACTIVITIES}
    others = [g for a in CHECK_ITEMS for g in graphs_of(a)]
    others += [g for a in ACTIVITIES.values() if a["id"] not in support_ids for g in graphs_of(a)]
    others += [
        graph_key(g["directed"], [(e["source"], e["target"]) for e in g["edges"]])
        for g in fixture("graphs.json")["graphs"]
    ]
    mine = support_graphs()
    assert len(mine) >= 8
    for g in mine:
        assert g not in others, sorted(map(str, g))


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.?])\s", text) if len(s) > 30]  # as #147's test does


def situations(a: dict[str, Any]) -> Iterator[str]:
    """What a support item is about: every option and item label, and each prompt sentence that
    names a graph's parts. A shared instruction ("Classify each graph as directed or undirected")
    is the skill, not the situation, and a parallel question shares it on purpose."""
    c = a["config"]
    for key in ("options", "left", "right"):
        yield from (o["label"] for o in c.get(key, []) if isinstance(o, dict))
    named = re.compile(rf"{EDGE.pattern}|\([A-Z]\)")
    yield from (s for s in sentences(c.get("prompt", "")) if named.search(s))


def test_no_support_text_restates_a_mastery_or_review_item() -> None:
    # Their situations: what an item shows before it is answered (prompt, options, test cases).
    theirs = [s for a in CHECK_ITEMS for t in plain_text(a["config"]) for s in sentences(t)]
    theirs += [s for seg in REVIEW_SEGMENTS for s in sentences(seg.get("body", ""))]
    for a in SUPPORT_ACTIVITIES:
        for mine in situations(a):
            for other in theirs:
                ratio = difflib.SequenceMatcher(None, mine.lower(), other.lower()).ratio()
                assert ratio < 0.6, (a["id"], mine, other)


def test_no_support_answer_is_a_mastery_answer() -> None:
    def labels(a: dict[str, Any]) -> set[str]:
        c = a["config"]
        items = [o for k in ("options", "left") for o in c.get(k, [])]
        return {o["label"] for o in items if isinstance(o, dict)}  # fill-in options are tokens

    theirs = set().union(*(labels(a) for a in CHECK_ITEMS))
    for a in SUPPORT_ACTIVITIES:
        assert not labels(a) & theirs, a["id"]
    # Nor does any support text spell out a mastery or review trace's order.
    for a in (a for a in CHECK_ITEMS if a["kind"] == "trace"):
        order = ", ".join(run_bfs(GraphScenarioOut(id=0, name="", **a["config"])).order)
        for b in SUPPORT_ACTIVITIES:
            assert all(order not in t for t in shown(b))
        assert all(order not in s["body"] for s in WORKED)
