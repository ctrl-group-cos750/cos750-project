"""The BFS engine (app/services/bfs.py). Pure, no database: these pin the traversal rules the
lessons teach, so the visualiser, the prediction and the trace table all agree (FR-6.5)."""

import pytest

from app.schemas.graphs import GraphScenarioOut
from app.services import bfs
from app.services.bfs import InvalidGraph, run_bfs


def scenario(**data: object) -> GraphScenarioOut:
    base: dict[str, object] = {"id": 1, "name": "s", "directed": False, "start_vertex": "A"}
    base.update(data)
    return GraphScenarioOut.model_validate(base)


def edges(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"source": s, "target": t} for s, t in pairs]


def test_single_vertex_visits_only_itself() -> None:
    result = run_bfs(scenario(vertices=["A"], edges=[]))
    assert result.order == ["A"]
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.visited_vertex == "A"
    assert step.queue == []
    assert step.discovered == []
    assert step.frontier_edges == []


def test_undirected_line_graph_in_order() -> None:
    # A - B - C, started at A: A then B then C.
    result = run_bfs(scenario(vertices=["A", "B", "C"], edges=edges(("A", "B"), ("B", "C"))))
    assert result.order == ["A", "B", "C"]
    # Edges are undirected, so B sees A again but A is already discovered: no re-enqueue.
    assert result.steps[1].visited_vertex == "B"
    assert result.steps[1].discovered == ["C"]


def test_neighbours_are_taken_in_alphabetical_order() -> None:
    # A joined to C, B and D in a deliberately unsorted edge list: they must come out B, C, D.
    result = run_bfs(
        scenario(
            vertices=["A", "B", "C", "D"],
            edges=edges(("A", "C"), ("A", "D"), ("A", "B")),
        )
    )
    assert result.order == ["A", "B", "C", "D"]
    first = result.steps[0]
    assert first.discovered == ["B", "C", "D"]
    assert first.queue == ["B", "C", "D"]
    assert [(e.source, e.target) for e in first.frontier_edges] == [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
    ]


def test_bfs_is_level_by_level() -> None:
    # A - B, A - C, B - D, C - D (diamond). Level order: A, then B C, then D once.
    result = run_bfs(
        scenario(
            vertices=["A", "B", "C", "D"],
            edges=edges(("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")),
        )
    )
    assert result.order == ["A", "B", "C", "D"]
    # D is discovered by B (the first to reach it), not enqueued twice by C.
    assert result.steps[1].visited_vertex == "B"
    assert result.steps[1].discovered == ["D"]
    assert result.steps[2].visited_vertex == "C"
    assert result.steps[2].discovered == []


def test_directed_edges_go_one_way_only() -> None:
    # A -> B but not B -> A; B -> C. Directed start A reaches A, B, C.
    result = run_bfs(
        scenario(directed=True, vertices=["A", "B", "C"], edges=edges(("A", "B"), ("B", "C")))
    )
    assert result.order == ["A", "B", "C"]
    # The same graph started at B (directed) cannot go back to A.
    result_from_b = run_bfs(
        scenario(
            directed=True,
            start_vertex="B",
            vertices=["A", "B", "C"],
            edges=edges(("A", "B"), ("B", "C")),
        )
    )
    assert result_from_b.order == ["B", "C"]


def test_disconnected_graph_visits_only_the_reachable_component() -> None:
    # A - B is one component; C - D another. From A, only A and B are reached.
    result = run_bfs(scenario(vertices=["A", "B", "C", "D"], edges=edges(("A", "B"), ("C", "D"))))
    assert result.order == ["A", "B"]
    assert "C" not in result.order
    assert "D" not in result.order


def test_self_loop_and_parallel_edges_do_not_revisit() -> None:
    # A self-loop on A and a doubled A-B edge must not enqueue anything twice.
    result = run_bfs(scenario(vertices=["A", "B"], edges=edges(("A", "A"), ("A", "B"), ("A", "B"))))
    assert result.order == ["A", "B"]
    assert result.steps[0].discovered == ["B"]


def test_unknown_start_vertex_is_rejected() -> None:
    with pytest.raises(InvalidGraph, match=bfs.UNKNOWN_START):
        run_bfs(scenario(start_vertex="Z", vertices=["A", "B"], edges=edges(("A", "B"))))


def test_duplicate_vertex_is_rejected() -> None:
    with pytest.raises(InvalidGraph, match=bfs.DUPLICATE_VERTEX):
        run_bfs(scenario(vertices=["A", "A", "B"], edges=[]))


def test_edge_to_unknown_vertex_is_rejected() -> None:
    with pytest.raises(InvalidGraph, match=bfs.UNKNOWN_EDGE_ENDPOINT):
        run_bfs(scenario(vertices=["A", "B"], edges=edges(("A", "Z"))))


def test_step_state_is_a_snapshot_not_a_live_reference() -> None:
    # Each step's queue/visited must be the state *after* that step, frozen, not mutated later.
    result = run_bfs(scenario(vertices=["A", "B", "C"], edges=edges(("A", "B"), ("B", "C"))))
    # After visiting A: B queued, visited is [A].
    assert result.steps[0].queue == ["B"]
    assert result.steps[0].visited == ["A"]
    # The final step's visited is the full order; earlier snapshots were not overwritten.
    assert result.steps[-1].visited == ["A", "B", "C"]
    assert result.steps[0].visited == ["A"]
