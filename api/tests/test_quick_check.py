"""Learner choice (#214): open modules, the recommended next module, the mastery check's opening
rule, the quick check ("Already know this?", FR-8.2) and moving on after two wrong answers (FR-2.7).

On the committed course (the fixtures, loaded as the seed loads them)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from support import complete_modules_before, wrong_answer

from app.models import (
    Activity,
    Attempt,
    Event,
    ModuleProgress,
    ObjectiveResult,
    PointsEntry,
    Segment,
    UserBadge,
)
from app.seed import load
from app.seed.demo_accounts import answer_for
from app.services.modules import ATTEMPTS_TO_MOVE_ON
from app.services.quick_check import PASS_MARK, QUICK_CHECK_SIZE

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}


@pytest.fixture
def committed(db: Session) -> Session:
    load(db)
    return db


def register(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def items(db: Session, module_id: int) -> list[Activity]:
    return list(
        db.scalars(
            select(Activity)
            .where(Activity.module_id == module_id, Activity.purpose == "test_out")
            .order_by(Activity.id)
        )
    )


def answers(db: Session, module_id: int, right: int) -> dict[str, Any]:
    """An answer for every question: the first `right` right, the rest wrong."""
    out = []
    for index, activity in enumerate(items(db, module_id)):
        correct = activity.solution["correct"]
        wrong = next(o["id"] for o in activity.config["options"] if o["id"] != correct)
        out.append({"activityId": activity.id, "selected": correct if index < right else wrong})
    return {"answers": out}


def take(client: TestClient, db: Session, module_id: int, right: int) -> Any:
    return client.post(f"/api/modules/{module_id}/quick-check", json=answers(db, module_id, right))


def statuses(client: TestClient) -> dict[int, str]:
    return {m["id"]: m["status"] for m in client.get("/api/modules").json()}


def recommended(client: TestClient) -> list[int]:
    return [m["id"] for m in client.get("/api/modules").json() if m["recommended"]]


def count(db: Session, model: Any, user_id: int) -> int:
    db.expire_all()
    return db.scalars(select(func.count()).select_from(model).where(model.user_id == user_id)).one()


# --- Open modules and the recommended path (FR-2.1) ----------------------------------------------


def test_a_new_student_may_open_any_module_but_the_mastery_check(
    client: TestClient, committed: Session
) -> None:
    register(client)
    assert statuses(client) == {0: "open", 1: "open", 2: "open", 3: "open", 4: "open", 5: "open",
                                6: "locked"}  # fmt: skip
    assert recommended(client) == [0]
    for module_id in range(6):
        assert client.get(f"/api/modules/{module_id}").status_code == 200
    assert client.get("/api/modules/6").status_code == 403
    checks = {m["id"]: m["quickCheck"] for m in client.get("/api/modules").json()}
    assert checks == {0: None, 1: "available", 2: "available", 3: "available", 4: "available",
                      5: "available", 6: None}  # fmt: skip


def test_the_mastery_check_opens_once_1_to_5_are_each_complete_or_tested_out(
    client: TestClient, committed: Session
) -> None:
    user_id = register(client)
    for module_id in (1, 2, 4):
        committed.add(ModuleProgress(user_id=user_id, module_id=module_id, status="complete"))
    committed.commit()
    assert statuses(client)[6] == "locked"
    assert recommended(client) == [3]  # the warm-up isn't sent back to once a later one is done
    assert take(client, committed, 3, QUICK_CHECK_SIZE).json()["passed"] is True
    assert statuses(client)[6] == "locked"
    assert take(client, committed, 5, PASS_MARK).json()["passed"] is True
    # Module 0, the warm-up, is not needed.
    assert statuses(client) == {0: "open", 1: "complete", 2: "complete", 3: "tested_out",
                                4: "complete", 5: "tested_out", 6: "open"}  # fmt: skip
    assert recommended(client) == [6]
    assert client.get("/api/modules/6").status_code == 200
    assert client.get("/api/activities/601").status_code == 200


# --- The quick check (FR-8.2) --------------------------------------------------------------------


def test_the_questions_carry_no_answers(client: TestClient, committed: Session) -> None:
    register(client)
    check = client.get("/api/modules/3/quick-check").json()
    assert check["available"] is True
    assert check["passMark"] == PASS_MARK == 3
    assert [q["id"] for q in check["questions"]] == [a.id for a in items(committed, 3)]
    assert len(check["questions"]) == QUICK_CHECK_SIZE == 4
    text = str(check)
    assert "correct" not in text
    assert "explanation" not in text
    assert "feedback" not in text
    assert check["result"] is None
    for module_id in (0, 6, 99):
        assert client.get(f"/api/modules/{module_id}/quick-check").status_code == 404


def test_a_pass_marks_the_module_tested_out_and_earns_nothing(
    client: TestClient, committed: Session
) -> None:
    user_id = register(client)
    result = take(client, committed, 2, PASS_MARK)
    assert result.status_code == 200
    body = result.json()
    assert (body["passed"], body["correct"], body["total"]) == (True, 3, 4)
    assert body["suggestion"] == "move_on"
    assert body["suggestedModule"] == 3
    assert body["lookAt"] == [items(committed, 2)[-1].title]
    assert [i["correct"] for i in body["items"]] == [True, True, True, False]
    assert all(i["explanation"] and i["answer"] for i in body["items"])

    module = next(m for m in client.get("/api/modules").json() if m["id"] == 2)
    assert (module["status"], module["quickCheck"]) == ("tested_out", "passed")
    # Testing out isn't working through: no module points, no First Module, no activity points,
    # no objective result, and no module segment done.
    assert count(committed, PointsEntry, user_id) == 0
    assert count(committed, UserBadge, user_id) == 0
    assert count(committed, ObjectiveResult, user_id) == 0
    assert all(not s["attempted"] for s in client.get("/api/modules/2").json()["segments"])
    # The answers are kept, and the event logged, for the evaluation.
    assert count(committed, Attempt, user_id) == 4
    event = committed.scalars(select(Event).where(Event.type == "quick_check_taken")).one()
    assert (event.ref, event.payload) == ("module:2", {"correct": 3, "total": 4, "passed": True})
    # It stays open, and its result can be read again.
    assert client.get("/api/modules/2").status_code == 200
    again = client.get("/api/modules/2/quick-check").json()
    assert again["available"] is False
    assert again["questions"] == []
    assert again["result"] == body


def test_one_attempt_per_module(client: TestClient, committed: Session) -> None:
    user_id = register(client)
    assert take(client, committed, 4, 2).status_code == 200
    second = take(client, committed, 4, QUICK_CHECK_SIZE)
    assert second.status_code == 409
    assert "one try per module" in second.json()["detail"]
    assert count(committed, Attempt, user_id) == 4
    assert statuses(client)[4] == "open"


def test_a_fail_with_two_right_suggests_working_through_the_module(
    client: TestClient, committed: Session
) -> None:
    register(client)
    body = take(client, committed, 1, 2).json()
    assert (body["passed"], body["suggestion"], body["suggestedModule"]) == (
        False,
        "work_through",
        1,
    )
    assert len(body["lookAt"]) == 2
    module = next(m for m in client.get("/api/modules").json() if m["id"] == 1)
    # Nothing is taken away or locked.
    assert (module["status"], module["quickCheck"]) == ("open", "not_passed")
    assert client.get("/api/modules/1").status_code == 200


def test_nearly_everything_wrong_suggests_the_module_before_if_it_isn_t_done(
    client: TestClient, committed: Session
) -> None:
    user_id = register(client)
    body = take(client, committed, 3, 1).json()
    assert (body["suggestion"], body["suggestedModule"]) == ("start_with", 2)
    # Module 2 done: the first question missed is on an objective module 3 first teaches.
    committed.add(ModuleProgress(user_id=user_id, module_id=2, status="complete"))
    committed.commit()
    again = client.get("/api/modules/3/quick-check").json()["result"]
    assert (again["suggestion"], again["suggestedModule"]) == ("work_through", 3)


def test_a_missed_objective_taught_earlier_points_there(
    client: TestClient, committed: Session
) -> None:
    """Module 4's first question is on objective 6, which module 2 first teaches."""
    register(client)
    assert items(committed, 4)[0].objective_id == 6
    # Wrong on the first two, right on the last two: two right is not "nearly everything wrong".
    body = answers(committed, 4, 0)
    for answer, activity in list(zip(body["answers"], items(committed, 4), strict=True))[2:]:
        answer["selected"] = activity.solution["correct"]
    result = client.post("/api/modules/4/quick-check", json=body).json()
    assert (result["correct"], result["suggestion"], result["suggestedModule"]) == (
        2,
        "start_with",
        2,
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a[:-1],  # one missing
        lambda a: [*a, a[0]],  # one twice
        lambda a: [*a[:-1], {**a[-1], "selected": "zz"}],  # no such option
        lambda a: [*a[:-1], {**a[-1], "activityId": 101}],  # not one of its questions
    ],
)
def test_answers_that_don_t_fit_are_refused_and_record_nothing(
    client: TestClient, committed: Session, change: Any
) -> None:
    user_id = register(client)
    body = answers(committed, 5, 4)
    response = client.post("/api/modules/5/quick-check", json={"answers": change(body["answers"])})
    assert response.status_code == 422
    assert count(committed, Attempt, user_id) == 0
    assert take(client, committed, 5, 4).status_code == 200  # the one try is still there


def test_a_module_worked_through_can_t_be_tested_out(
    client: TestClient, committed: Session
) -> None:
    user_id = register(client)
    committed.add(ModuleProgress(user_id=user_id, module_id=1, status="complete"))
    committed.commit()
    assert client.get("/api/modules/1/quick-check").json()["available"] is False
    assert take(client, committed, 1, 4).status_code == 409
    module = next(m for m in client.get("/api/modules").json() if m["id"] == 1)
    assert module["quickCheck"] is None


def test_a_tested_out_module_worked_through_completes_and_earns_its_points(
    client: TestClient, committed: Session
) -> None:
    """Working through a module after testing out of it is real work (#214)."""
    user_id = register(client)
    assert take(client, committed, 1, 4).json()["passed"] is True
    module = client.get("/api/modules/1").json()
    assert module["status"] == "tested_out"
    # Answer every activity right and walk to the end.
    for segment in module["segments"]:
        if segment["activityId"] and segment["shown"]:
            activity = committed.get_one(Activity, segment["activityId"])
            assert (
                client.post(
                    f"/api/activities/{activity.id}/attempts",
                    json={"submitted": answer_for(activity, "right", "test")},
                ).status_code
                == 201
            )
    shown = [s["position"] for s in module["segments"] if s["shown"]]
    for position in shown:
        assert (
            client.post("/api/modules/1/position", json={"segmentPosition": position}).status_code
            == 200
        )
    client.post("/api/modules/1/position", json={"segmentPosition": shown[-1]})
    assert statuses(client)[1] == "complete"
    assert (
        committed.scalars(
            select(PointsEntry.points).where(
                PointsEntry.user_id == user_id, PointsEntry.ref == "module:1"
            )
        ).one()
        == 25
    )


# --- Moving on after two wrong answers (FR-2.7) --------------------------------------------------


def first_activity_segment(db: Session, module_id: int) -> Segment:
    return db.scalars(
        select(Segment)
        .join(Activity, Activity.id == Segment.activity_id)
        .where(
            Segment.module_id == module_id,
            Segment.support_for.is_(None),
            Activity.purpose == "practice",
        )
        .order_by(Segment.position)
    ).first()  # type: ignore[return-value]


def test_two_wrong_answers_let_the_student_move_on_without_a_reward(
    client: TestClient, committed: Session
) -> None:
    user_id = register(client)
    segment = first_activity_segment(committed, 1)
    activity = committed.get_one(Activity, segment.activity_id)
    assert ATTEMPTS_TO_MOVE_ON == 2

    def detail() -> dict[str, Any]:
        found = client.get("/api/modules/1").json()["segments"]
        return next(s for s in found if s["id"] == segment.id)

    # Reach the segment: its place in the module, as the page counts it.
    index = next(
        s["position"]
        for s in client.get("/api/modules/1").json()["segments"]
        if s["id"] == segment.id
    )
    for position in range(1, index + 1):
        client.post("/api/modules/1/position", json={"segmentPosition": position})
    body = {"submitted": wrong_answer(activity)}
    assert client.post(f"/api/activities/{activity.id}/attempts", json=body).status_code == 201
    assert (detail()["done"], detail()["lookAgain"]) == (False, False)
    blocked = client.post("/api/modules/1/position", json={"segmentPosition": index + 1})
    assert blocked.status_code == 409
    assert client.post(f"/api/activities/{activity.id}/attempts", json=body).status_code == 201
    assert (detail()["done"], detail()["lookAgain"]) == (True, True)
    moved = client.post("/api/modules/1/position", json={"segmentPosition": index + 1})
    assert moved.status_code == 200, moved.text
    # Still not right: no points, and the activity is not solved.
    assert count(committed, PointsEntry, user_id) == 0
    assert client.get(f"/api/activities/{activity.id}").json()["solved"] is False


def test_the_mastery_check_still_takes_one_answer(client: TestClient, committed: Session) -> None:
    register(client)
    complete_modules_before(committed, STUDENT["email"], 6)
    item = committed.get_one(Activity, 601)
    body = {"submitted": wrong_answer(item)}
    assert client.post("/api/activities/601/attempts", json=body).status_code == 201
    assert client.post("/api/activities/601/attempts", json=body).status_code == 409
