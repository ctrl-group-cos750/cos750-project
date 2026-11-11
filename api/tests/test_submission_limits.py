"""Bounded answer and hint submissions, and ids that can't name a row (#139; NFR-S6, NFR-U3).

Each kind's submission shape bounds its sizes, the whole stored submission is capped, answers and
hint reveals are rate-limited per student, and an id past a Postgres integer is a 422, not a
plain-text 500. Run on Postgres too (TEST_DATABASE_URL), where the int4 overflow was real.
"""

import itertools
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from support import open_module
from test_mastery import correct_submission

from app.models import Activity, Attempt, Hint
from app.routers import activities as activities_router
from app.routers.activities import attempts_limiter, hints_limiter
from app.schemas.activities import (
    MAX_SUBMISSION_BYTES,
    TRACE_LABEL,
    TRACE_VERTICES,
    TraceConfig,
    TraceSubmission,
)
from app.schemas.base import ApiModel
from app.seed import read_fixtures

STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
OTHER = {"email": "bo@example.com", "password": "Correct horse 2", "displayName": "Bo"}
BIG = 2**31


def make(db: Session, kind: str, config: dict[str, Any], solution: dict[str, Any]) -> int:
    activity = Activity(
        kind=kind,
        title=kind,
        visible=True,
        config=config,
        solution=solution,
        module_id=open_module(db),
    )
    db.add(activity)
    db.flush()
    db.add_all(Hint(activity_id=activity.id, level=n, body=f"Hint {n}") for n in (1, 2, 3, 4))
    db.commit()
    return activity.id


MC = ("multiple_choice", {"prompt": "Q", "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]}, {"correct": "a"})  # fmt: skip
FILL = ("fill_in", {"code": "x = __1__", "blanks": [1], "options": ["1", "2"]}, {"answers": {"1": "1"}})  # fmt: skip
MATCHING = ("matching", {"prompt": "Q", "left": [{"id": "l", "label": "L"}], "right": [{"id": "r", "label": "R"}]}, {"pairs": {"l": "r"}})  # fmt: skip
PARSONS = ("parsons", {"lines": [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}]}, {"order": [1, 2]})  # fmt: skip
TRACE: tuple[str, dict[str, Any], dict[str, Any]] = ("trace", {"directed": False, "vertices": ["A", "B"], "edges": [{"source": "A", "target": "B"}], "startVertex": "A"}, {})  # fmt: skip


@pytest.fixture
def student(client: TestClient, db: Session) -> TestClient:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return client


def attempts(db: Session) -> int:
    db.expire_all()
    return db.scalars(select(func.count()).select_from(Attempt)).one()


# --- Sizes, per kind ----------------------------------------------------------------------------

CONTROL = "x\x00y"


@pytest.mark.parametrize(
    ("activity", "submitted"),
    [
        (MC, {"selected": "a" * 51}),
        (MC, {"selected": CONTROL}),
        (MC, {"selected": 1}),
        (MC, {"selected": ["a"]}),
        (FILL, {"answers": {str(n): "1" for n in range(101)}}),  # more blanks than any config
        (FILL, {"answers": {"1": "x" * 201}}),  # longer than any token may be
        (FILL, {"answers": {"1": CONTROL}}),
        (FILL, {"answers": {"1": "a\nb"}}),
        (FILL, {"answers": {str(BIG): "1"}}),
        (FILL, {"answers": {"one": "1"}}),
        (FILL, {"answers": ["1"]}),
        (MATCHING, {"pairs": {"l": "r" * 51}}),
        (MATCHING, {"pairs": {"l" * 51: "r"}}),
        (MATCHING, {"pairs": {f"l{n}": "r" for n in range(21)}}),
        (MATCHING, {"pairs": {"l": "\x7f"}}),
        (PARSONS, {"order": [BIG]}),
        (PARSONS, {"order": [-BIG - 1]}),
        (PARSONS, {"order": list(range(101))}),
        (PARSONS, {"order": ["one"]}),
        (TRACE, {"rows": [{"visitedVertex": "A\x00", "queue": [], "visited": [], "order": []}]}),
        (MC, {"selected": "a", "note": "x"}),  # unknown fields are refused, not stored
        (MC, {}),
    ],
)
def test_an_oversized_or_malformed_submission_is_422_and_not_stored(
    student: TestClient, db: Session, activity: tuple[str, Any, Any], submitted: Any
) -> None:
    activity_id = make(db, *activity)
    response = student.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": submitted}
    )
    assert response.status_code == 422, response.text
    assert attempts(db) == 0


def test_a_submission_that_is_not_an_object_is_422(student: TestClient, db: Session) -> None:
    activity_id = make(db, *MC)
    bodies: list[Any] = [{"submitted": "a"}, {"submitted": None}, {"submitted": ["a"]}, {}, []]
    for body in bodies:
        assert student.post(f"/api/activities/{activity_id}/attempts", json=body).status_code == 422
    assert attempts(db) == 0


def test_a_trace_table_larger_than_its_graph_could_need_is_422(
    student: TestClient, db: Session
) -> None:
    """A trace graph has at most 20 vertices with 12-character labels, so a table of more rows,
    longer lists or longer labels can't be an answer to one."""
    activity_id = make(db, *TRACE)
    label = "V" * 12
    row: dict[str, Any] = {"visitedVertex": label, "queue": [label] * 20, "visited": [label] * 20,
           "order": [label] * 20}  # fmt: skip
    for submitted in (
        {"rows": [row] * 21},
        {"rows": [{**row, "queue": [label] * 21}]},
        {"rows": [{**row, "visitedVertex": "V" * 13}]},
    ):
        response = student.post(
            f"/api/activities/{activity_id}/attempts", json={"submitted": submitted}
        )
        assert response.status_code == 422
    # The largest table the shape allows is still graded (wrong), not refused for its size.
    largest = {"rows": [row] * 20}
    assert len(json.dumps(largest, separators=(",", ":"))) < MAX_SUBMISSION_BYTES
    response = student.post(f"/api/activities/{activity_id}/attempts", json={"submitted": largest})
    assert response.status_code == 201
    assert attempts(db) == 1


def test_padding_past_the_cap_is_413_and_not_stored(student: TestClient, db: Session) -> None:
    """The analysis stored 900 kB of padding in an unknown field; now it is refused unread."""
    padded = {"selected": "a", "note": "x" * 900_000}
    response = student.post(f"/api/activities/{make(db, *MC)}/attempts", json={"submitted": padded})
    assert response.status_code == 413
    assert response.json() == {"detail": "This answer is too long to check."}
    assert attempts(db) == 0


def largest_valid(kind: str) -> dict[str, Any]:
    """The biggest submission each kind's shape accepts (compact JSON)."""
    big_int = -(2**31)
    match kind:
        case "multiple_choice":
            return {"selected": "x" * 50}
        case "parsons":
            return {"order": [big_int] * 100}
        case "fix_the_bug":
            return {"order": [big_int] * 150}
        case "fill_in":
            return {"answers": {str(big_int + n): "x" * 200 for n in range(100)}}
        case "matching":
            return {"pairs": {f"{n:02d}" + "l" * 48: "r" * 50 for n in range(20)}}
        case "choose_tests":
            return {"selected": ["t" * 50] * 8}
        case "trace":
            label = "V" * 12
            row = {"visitedVertex": label, "queue": [label] * 20, "visited": [label] * 20,
                   "order": [label] * 20}  # fmt: skip
            return {"rows": [row] * 20}
    raise AssertionError(kind)


@pytest.mark.parametrize(
    "kind",
    ["multiple_choice", "parsons", "fix_the_bug", "fill_in", "matching", "choose_tests", "trace"],
)
def test_the_cap_never_refuses_a_submission_its_shape_accepts(kind: str) -> None:
    """MAX_SUBMISSION_BYTES is only a backstop: every valid submission of every kind fits."""
    import app.schemas.activities as schemas

    shapes: dict[str, type[ApiModel]] = {
        "multiple_choice": schemas.MultipleChoiceSubmission,
        "parsons": schemas.ParsonsSubmission,
        "fix_the_bug": schemas.FixTheBugSubmission,
        "fill_in": schemas.FillInSubmission,
        "matching": schemas.MatchingSubmission,
        "choose_tests": schemas.ChooseTestsSubmission,
        "trace": schemas.TraceSubmission,
    }
    submitted = largest_valid(kind)
    shapes[kind].model_validate(submitted)  # it is valid
    assert len(json.dumps(submitted, separators=(",", ":"))) < MAX_SUBMISSION_BYTES


def test_the_worst_right_trace_answer_fits_the_cap_with_room() -> None:
    """The right answer to the largest trace graph TraceConfig allows (20 vertices, 12-character
    labels), from the BFS engine, for the shapes that make the table longest."""
    vertices = [f"V{n:011d}" for n in range(TRACE_VERTICES)]
    assert {len(v) for v in vertices} == {TRACE_LABEL}
    shapes = {
        "complete": list(itertools.combinations(vertices, 2)),
        "star": [(vertices[0], v) for v in vertices[1:]],
        "path": list(itertools.pairwise(vertices)),
    }
    sizes = {}
    for name, edges in shapes.items():
        config = {
            "directed": False,
            "vertices": vertices,
            "edges": [{"source": a, "target": b} for a, b in edges],
            "startVertex": vertices[0],
        }
        TraceConfig.model_validate(config)
        answer = correct_submission(Activity(kind="trace", config=config, solution={}))
        TraceSubmission.model_validate(answer)
        sizes[name] = len(json.dumps(answer, separators=(",", ":")))
    assert max(sizes.values()) * 3 < MAX_SUBMISSION_BYTES, sizes


@pytest.mark.parametrize(
    "change",
    [
        {"vertices": [f"v{n}" for n in range(21)]},
        {"vertices": ["A" * 13, "B"]},
    ],
)
def test_a_trace_graph_too_big_to_trace_by_hand_is_refused_in_content(
    change: dict[str, Any],
) -> None:
    from pydantic import ValidationError

    config = {**TRACE[1], **change}
    with pytest.raises(ValidationError):
        TraceConfig.model_validate(config)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        ("ChoiceOption", {"id": "a\x00", "label": "A"}),
        ("MatchingItem", {"id": "l\n", "label": "L"}),
        ("FillInConfig", {"code": "__1__", "blanks": [1], "options": ["ok", "tab\there"]}),
        ("MultipleChoiceSolution", {"correct": "a\x7f"}),
        ("MatchingSolution", {"pairs": {"l": "r\x01"}}),
        ("ChooseTestsSolution", {"exposing": ["t\x00"]}),
        ("FillInSolution", {"answers": {"1": "x\ny"}}),
    ],
)
def test_content_cannot_hold_a_choice_a_student_would_be_refused_for(
    model: str, data: dict[str, Any]
) -> None:
    """The same no-control-characters rule as the submissions, on the content side (#139)."""
    from pydantic import ValidationError

    import app.schemas.activities as schemas

    with pytest.raises(ValidationError):
        getattr(schemas, model).model_validate(data)


@pytest.mark.parametrize(
    ("activity", "submitted"),
    [
        (MC, {"selected": "a" * 50}),  # the longest an option id may be: a wrong answer
        (FILL, {"answers": {"1": "x" * 200}}),
        (FILL, {"answers": {}}),
        (MATCHING, {"pairs": {}}),
        (PARSONS, {"order": []}),
        (PARSONS, {"order": [BIG - 1, -BIG]}),
        (TRACE, {"rows": [{"visitedVertex": "Z", "queue": [], "visited": [], "order": []}]}),
    ],
)
def test_bounded_and_empty_submissions_are_graded_as_wrong(
    student: TestClient, db: Session, activity: tuple[str, Any, Any], submitted: Any
) -> None:
    """At the limits, or empty, an answer is still an answer (FR-2.7): graded, wrong, stored."""
    activity_id = make(db, *activity)
    response = student.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": submitted}
    )
    assert response.status_code == 201, response.text
    assert response.json()["correct"] is False
    assert attempts(db) == 1


def test_every_committed_activitys_answer_fits_well_under_the_cap() -> None:
    """The cap is far above anything the content asks for (MAX_SUBMISSION_BYTES's comment)."""
    content = read_fixtures()
    sizes = {
        a.id: len(
            json.dumps(
                correct_submission(Activity(**a.model_dump(exclude={"hints"}))),
                separators=(",", ":"),
            )
        )
        for a in content.activities
    }
    assert max(sizes.values()) * 30 < MAX_SUBMISSION_BYTES, max(sizes.values())


def test_a_fill_in_token_longer_than_200_is_refused_in_content() -> None:
    from pydantic import ValidationError

    from app.schemas.activities import FillInConfig

    with pytest.raises(ValidationError):
        FillInConfig(code="__1__", blanks=[1], options=["x" * 201])


# --- Rate limits (NFR-S6) -----------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(attempts_limiter, "clock", fake)
    monkeypatch.setattr(hints_limiter, "clock", fake)
    return fake


def test_sixty_answers_a_minute_then_429(client: TestClient, db: Session, clock: Clock) -> None:
    activity_id = make(db, *MC)
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    answer = {"submitted": {"selected": "b"}}
    for _ in range(60):
        assert (
            client.post(f"/api/activities/{activity_id}/attempts", json=answer).status_code == 201
        )
    refused = client.post(f"/api/activities/{activity_id}/attempts", json=answer)
    assert refused.status_code == 429
    assert refused.headers["Retry-After"] == "60"
    assert refused.json() == {"detail": "You're answering very fast. Wait a moment and try again."}
    assert attempts(db) == 60

    # Another student isn't affected.
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json=OTHER).status_code == 201
    assert client.post(f"/api/activities/{activity_id}/attempts", json=answer).status_code == 201

    # A minute later the first student may answer again.
    clock.now += 60
    client.post("/api/auth/logout")
    login = {"email": STUDENT["email"], "password": STUDENT["password"]}
    assert client.post("/api/auth/login", json=login).status_code == 200
    assert client.post(f"/api/activities/{activity_id}/attempts", json=answer).status_code == 201


def test_a_fast_but_human_student_is_never_limited(
    student: TestClient, db: Session, clock: Clock
) -> None:
    """One answer every second for ten minutes, with a hint every two seconds: never refused."""
    activity_id = make(db, *MC)
    answer = {"submitted": {"selected": "b"}}
    for second in range(600):
        clock.now += 1
        assert (
            student.post(f"/api/activities/{activity_id}/attempts", json=answer).status_code == 201
        )
        if second % 2 == 0:
            assert student.post(f"/api/activities/{activity_id}/hints").status_code in (201, 409)


def test_thirty_hint_requests_a_minute_then_429(
    student: TestClient, db: Session, clock: Clock
) -> None:
    activity_id = make(db, *MC)
    codes = [student.post(f"/api/activities/{activity_id}/hints").status_code for _ in range(30)]
    assert codes == [201] * 4 + [409] * 26
    refused = student.post(f"/api/activities/{activity_id}/hints")
    assert refused.status_code == 429
    assert "Retry-After" in refused.headers
    # Reading the hints already shown is never limited.
    assert student.get(f"/api/activities/{activity_id}/hints").status_code == 200


# --- Ids that can't name a row (NFR-U3) ---------------------------------------------------------


@pytest.mark.parametrize("bad", [BIG, 2**63, 10**30, -1])
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/activities/{}"),
        ("POST", "/api/activities/{}/attempts"),
        ("GET", "/api/activities/{}/hints"),
        ("POST", "/api/activities/{}/hints"),
        ("GET", "/api/videos/{}"),
        ("GET", "/api/graphs/{}"),
        ("GET", "/api/graphs/{}/bfs"),
        ("GET", "/api/me/review/{}"),
        ("GET", "/api/modules/{}"),
        ("POST", "/api/modules/{}/position"),
    ],
)
def test_an_id_past_a_postgres_integer_is_422_json(
    student: TestClient, db: Session, method: str, path: str, bad: int
) -> None:
    body: dict[str, Any] | None = None
    if path.endswith("attempts"):
        body = {"submitted": {"selected": "a"}}
    elif path.endswith("position"):
        body = {"segmentPosition": 0}
    response = student.request(method, path.format(bad), json=body)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert response.json()["detail"][0]["loc"][0] == "path"


def test_an_event_for_an_id_past_a_postgres_integer_is_422(student: TestClient) -> None:
    body = {"type": "video_started", "targetId": BIG}
    assert student.post("/api/events", json=body).status_code == 422


def test_the_largest_postgres_integer_is_a_plain_404(student: TestClient, db: Session) -> None:
    assert student.get(f"/api/activities/{BIG - 1}").status_code == 404
    assert student.get(f"/api/videos/{BIG - 1}").status_code == 404


# --- When the database refuses anyway -----------------------------------------------------------


@pytest.mark.parametrize(
    ("error", "status", "detail"),
    [
        (DataError, 422, "Something in this request is out of range. Check it and try again."),
        (
            IntegrityError,
            409,
            "This changed at the same moment somewhere else. Reload the page and try again.",
        ),
        (OperationalError, 503, "Ctrl Academy is busy. Try again in a moment."),
        (SQLAlchemyError, 500, "Something went wrong on our side. Try again in a moment."),
    ],
)
def test_a_database_error_is_json_for_the_student(
    student: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    error: type[SQLAlchemyError],
    status: int,
    detail: str,
) -> None:
    """Before, any of these was a plain-text 500 and a dropped connection."""

    def fail(*_: Any) -> None:
        if error is SQLAlchemyError:
            raise SQLAlchemyError("boom")
        raise error("SELECT 1", {}, Exception("boom"))

    monkeypatch.setattr(activities_router, "record_attempt", fail)
    activity_id = make(db, *MC)
    response = student.post(
        f"/api/activities/{activity_id}/attempts", json={"submitted": {"selected": "a"}}
    )
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    if status == 503:
        assert response.headers["Retry-After"] == "2"


def test_a_conflict_logs_the_constraint_that_refused_it(
    student: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Diag:
        constraint_name = "points_entries_user_id_ref_key"

    class Orig(Exception):
        diag = Diag()

    def fail(*_: Any) -> None:
        raise IntegrityError("INSERT", {}, Orig("duplicate"))

    monkeypatch.setattr(activities_router, "record_attempt", fail)
    activity_id = make(db, *MC)
    with caplog.at_level("WARNING", logger="app.errors"):
        response = student.post(
            f"/api/activities/{activity_id}/attempts", json={"submitted": {"selected": "a"}}
        )
    assert response.status_code == 409
    assert "points_entries_user_id_ref_key" in caplog.text
