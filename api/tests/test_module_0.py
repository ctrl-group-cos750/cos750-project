"""Module 0 (Warm-up and queue refresher, #26): the diagnostic warm-up before BFS.

Module 0 is different from the others: its activities are *diagnostics* (purpose "diagnostic", no
objective), each one gating a refresher the student skips when they answer it right (FR-8.1). So
the checks here are the content rules from issue #26: three diagnostics on queues, Python basics
and loops, each with four hint levels and feedback for every wrong answer, and a refresher for each
that a real diagnostic skips, plus the invariant that a diagnostic carries no objective.
"""

import pytest

from app.seed import ActivityFixture, FixtureFile, read_fixtures

CONTENT: FixtureFile = read_fixtures()
MODULE = next(m for m in CONTENT.modules if m.id == 0)
ACTIVITIES = [a for a in CONTENT.activities if a.module_id == 0]


def test_every_activity_is_shown_once_and_gates_a_refresher() -> None:
    shown = [s.activity_id for s in MODULE.segments if s.activity_id is not None]
    skip_checks = [s.skip_check_activity_id for s in MODULE.segments if s.skip_check_activity_id]
    # Each diagnostic appears once as its own activity segment, and once as the skip-check of the
    # refresher it gates.
    assert sorted(shown) == sorted(a.id for a in ACTIVITIES)
    assert sorted(skip_checks) == sorted(a.id for a in ACTIVITIES)


def test_the_module_opens_with_an_intro_and_ends_ready_for_module_1() -> None:
    first, last = MODULE.segments[0], MODULE.segments[-1]
    assert first.kind == "text"
    assert last.kind == "text"
    # It names the three things BFS builds on, so the warm-up's purpose is clear up front.
    assert all(word in first.body for word in ("queue", "list", "loop"))


def test_every_activity_is_a_diagnostic_with_no_objective() -> None:
    # A diagnostic tests prior knowledge, which belongs to no learning objective (FR-8.1): the
    # seed loader rejects a diagnostic that carries one, so this guards the module's intent.
    for a in ACTIVITIES:
        assert a.purpose == "diagnostic"
        assert a.objective_id is None


def test_every_refresher_is_gated_by_a_real_diagnostic_on_its_topic() -> None:
    diagnostics = {a.id for a in ACTIVITIES}
    refreshers = [s for s in MODULE.segments if s.kind == "refresher"]
    # Three topics, one refresher each, each skipped by a diagnostic that exists.
    assert {s.refresher_for for s in refreshers} == {"queues", "python-basics", "loops"}
    for s in refreshers:
        assert s.skip_check_activity_id in diagnostics
        assert s.body.strip()


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_activity_has_four_hint_levels_and_the_last_gives_the_answer(
    a: ActivityFixture,
) -> None:
    assert [h.level for h in a.hints] == [1, 2, 3, 4]
    assert a.hints[-1].body.startswith("Answer:")


@pytest.mark.parametrize("a", ACTIVITIES, ids=lambda a: str(a.id))
def test_every_wrong_answer_has_feedback(a: ActivityFixture) -> None:
    wrong = {o["id"] for o in a.config["options"]} - {a.solution["correct"]}
    assert set(a.solution["feedback"]) == wrong
