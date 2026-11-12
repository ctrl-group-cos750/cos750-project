"""Content from #150: subgoal labels, self-explanation items after the worked examples, and
misconception items whose distractors are what buggy BFS programs give (Seppälä et al. 2006).

The buggy variants below are run on each item's graph, so a distractor can't drift away from the
misconception its feedback names.
"""

import re
from collections import deque
from collections.abc import Callable

import pytest

from app.seed import ActivityFixture, FixtureFile, read_fixtures

CONTENT: FixtureFile = read_fixtures()
ACTIVITIES = {a.id: a for a in CONTENT.activities}
MODULES = {m.id: m for m in CONTENT.modules}
SUBGOALS = ["initialise", "take the next vertex", "for each neighbour", "mark and enqueue"]
Lists = dict[str, list[str]]


def bfs(adj: Lists, start: str, *, sort: bool = False) -> tuple[list[str], list[list[str]]]:
    """BFS with the module's code: the order, and the queue after each vertex leaves."""
    found, queue, order, queues = {start}, deque([start]), [], []
    while queue:
        v = queue.popleft()
        order.append(v)
        for n in sorted(adj[v]) if sort else adj[v]:
            if n not in found:
                found.add(n)
                queue.append(n)
        queues.append(list(queue))
    return order, queues


def alphabetical(adj: Lists, start: str) -> tuple[list[str], list[list[str]]]:
    """The misconception that BFS order is alphabetical (Tilanterä et al. 2025)."""
    return bfs(adj, start, sort=True)


def stack(adj: Lists, start: str) -> tuple[list[str], list[list[str]]]:
    """The same code with a stack: the vertex that joined last leaves next."""
    found, waiting, order, states = {start}, [start], [], []
    while waiting:
        v = waiting.pop()
        order.append(v)
        for n in adj[v]:
            if n not in found:
                found.add(n)
                waiting.append(n)
        states.append(list(waiting))
    return order, states


def mark_on_dequeue(adj: Lists, start: str) -> tuple[list[str], list[list[str]]]:
    """A vertex is marked only when it leaves, so one that is waiting can join again."""
    marked: set[str] = set()
    queue, order, queues = deque([start]), [], []
    while queue:
        v = queue.popleft()
        if v not in marked:
            marked.add(v)
            order.append(v)
            queue.extend(n for n in adj[v] if n not in marked)
        queues.append(list(queue))
    return order, queues


def dfs(adj: Lists, start: str) -> tuple[list[str], list[list[str]]]:
    order: list[str] = []

    def go(v: str) -> None:
        order.append(v)
        for n in adj[v]:
            if n not in order:
                go(n)

    go(start)
    return order, []


def stored_lists(prompt: str) -> Lists:
    """The neighbour lists a prompt gives, as "A: D, B." in the order stored."""
    return {v: ns.split(", ") for v, ns in re.findall(r"\b([A-Z]): ([A-Z](?:, [A-Z])*)\.", prompt)}


def edges(prompt: str) -> set[frozenset[str]]:
    return {frozenset(e) for e in re.findall(r"\b([A-Z])\N{EN DASH}([A-Z])\b", prompt)}


def labels(a: ActivityFixture) -> dict[str, str]:
    return {o["id"]: o["label"] for o in a.config["options"]}


Variant = Callable[[Lists, str], tuple[list[str], list[list[str]]]]
# item: (start, what is asked, {option id: (variant, the misconception its feedback names)})
MISCONCEPTIONS: dict[
    int,
    tuple[
        str,
        Callable[[tuple[list[str], list[list[str]]]], list[str]],
        dict[str, tuple[Variant, str]],
    ],
] = {
    461: (
        "A",
        lambda run: run[0],
        {
            "b": (bfs, ""),
            "a": (alphabetical, "alphabetical"),
            "c": (dfs, "depth-first"),
            "d": (stack, "stack"),
        },
    ),
    462: (
        "K",
        lambda run: run[1][1],  # the queue after the second vertex leaves
        {
            "d": (bfs, ""),
            "b": (alphabetical, "alphabetical"),
            "c": (stack, "stack"),
            "a": (mark_on_dequeue, "marked only when it leaves"),
        },
    ),
}


@pytest.mark.parametrize("item", MISCONCEPTIONS)
def test_each_option_is_what_bfs_or_a_buggy_bfs_gives(item: int) -> None:
    a = ACTIVITIES[item]
    prompt = a.config["prompt"]
    adj = stored_lists(prompt)
    # The lists are the graph's edges, both ways, and not in alphabetical order.
    assert {frozenset((v, n)) for v, ns in adj.items() for n in ns} == edges(prompt)
    assert all(v in adj[n] for v, ns in adj.items() for n in ns)
    assert any(ns != sorted(ns) for ns in adj.values())
    start, answer, options = MISCONCEPTIONS[item]
    assert set(options) == set(labels(a))
    given = {
        option: ", ".join(answer(variant(adj, start))) for option, (variant, _) in options.items()
    }
    assert given == labels(a)
    assert len(set(given.values())) == len(given)  # every bug gives its own answer
    assert a.solution["correct"] == next(o for o, (v, _) in options.items() if v is bfs)
    for option, (_, name) in options.items():
        if name:
            assert name in a.solution["feedback"][option].lower(), option


def test_the_order_is_the_engines_when_the_lists_are_sorted() -> None:
    """The variant code is the module's code: with sorting it gives module 3's campus order."""
    campus = {
        "A": ["C", "E"],
        "B": ["C", "G"],
        "C": ["A", "B", "F"],
        "D": ["E"],
        "E": ["A", "D", "F"],
        "F": ["C", "E"],
        "G": ["B"],
    }
    assert bfs(campus, "A", sort=True)[0] == ["A", "C", "E", "B", "F", "D", "G"]


@pytest.mark.parametrize(("module", "item"), [(1, 160), (2, 260), (3, 360), (4, 460)])
def test_a_why_question_follows_each_worked_example(module: int, item: int) -> None:
    """Self-explanation (Atkinson et al. 2000), then the module's next practice item as near
    transfer."""
    segments = MODULES[module].segments
    worked = next(i for i, s in enumerate(segments) if s.kind == "worked_example")
    assert segments[worked + 1].activity_id == item
    assert ACTIVITIES[item].config["prompt"].startswith("In ")
    assert "Why" in ACTIVITIES[item].config["prompt"]
    after = ACTIVITIES[segments[worked + 2].activity_id or 0]
    assert after.purpose == "practice"


def test_the_bfs_worked_examples_name_the_subgoals() -> None:
    """Subgoal labels (Margulieux et al. 2012; Morrison et al. 2015, 2016)."""
    for module in (3, 4):
        worked = next(s for s in MODULES[module].segments if s.kind == "worked_example")
        text = worked.body.lower()
        assert all(goal in text for goal in SUBGOALS), module
    parsons = next(s for s in MODULES[4].segments if s.activity_id == 404)
    assert all(goal in parsons.title.lower() for goal in SUBGOALS)
    assert all(goal in ACTIVITIES[404].hints[0].body.lower() for goal in SUBGOALS)


@pytest.mark.parametrize("item", [160, 260, 360, 460, 461, 462])
def test_new_items_have_the_full_ladder_and_feedback_for_every_wrong_option(item: int) -> None:
    a = ACTIVITIES[item]
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")
    wrong = set(labels(a)) - {a.solution["correct"]}
    assert set(a.solution["feedback"]) == wrong
    assert all(f.startswith("Not quite.") for f in a.solution["feedback"].values())
    assert a.solution["explanation"]
