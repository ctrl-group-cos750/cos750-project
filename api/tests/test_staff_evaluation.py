"""Evaluation data for the pilot (GET /api/staff/export/{table}.csv and /api/staff/insights):
staff only, student accounts only, internal ids only, and safe to open in a spreadsheet."""

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Hint, User, Video

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)


def make_video(db: Session, first_title: str = "Which leaves first?") -> tuple[int, int, int]:
    """A video with two multiple-choice checkpoints (correct: a), each with hints 1 to 4."""

    def choice(title: str) -> Activity:
        options = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
        return Activity(
            kind="multiple_choice",
            title=title,
            visible=True,
            config={"prompt": title, "options": options},
            solution={"correct": "a", "feedback": {}},
        )

    first, second = choice(first_title), choice("What stops a loop?")
    video = Video(
        title="Meet BFS",
        media_path="/media/videos/meet-bfs.mp4",
        captions_path="/media/videos/meet-bfs.vtt",
        transcript="Words",
        duration_seconds=60,
    )
    db.add_all([first, second, video])
    db.flush()
    db.add_all(
        [
            Checkpoint(video_id=video.id, at_seconds=20, activity_id=first.id),
            Checkpoint(video_id=video.id, at_seconds=45, activity_id=second.id),
            *[Hint(activity_id=first.id, level=n, body=f"hint {n}") for n in range(1, 5)],
        ]
    )
    db.commit()
    return video.id, first.id, second.id


def register(client: TestClient, email: str) -> int:
    client.cookies.clear()
    body = {"email": email, "password": PASSWORD, "displayName": email.split("@")[0].title()}
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201
    return int(response.json()["id"])


def answer(client: TestClient, activity_id: int, option: str) -> None:
    body = {"submitted": {"selected": option}}
    assert client.post(f"/api/activities/{activity_id}/attempts", json=body).status_code == 201


def hints(client: TestClient, activity_id: int, n: int) -> None:
    for _ in range(n):
        assert client.post(f"/api/activities/{activity_id}/hints").status_code == 201


def become_staff(client: TestClient, db: Session, email: str) -> int:
    user_id = register(client, email)
    user = db.get(User, user_id)
    assert user is not None
    user.is_staff = True
    db.commit()
    return user_id


def pilot(client: TestClient, db: Session) -> dict[str, int]:
    """Ada: wrong, hints up to 3, right, then passes the second too. Alan: right first time on the
    first, then stops. Grace (staff) answers too, and must not be counted."""
    _, first, second = make_video(db)
    ids = {"first": first, "second": second}
    ids["ada"] = register(client, "ada@example.com")
    answer(client, first, "b")
    hints(client, first, 3)
    answer(client, first, "a")
    answer(client, second, "a")
    ids["alan"] = register(client, "alan@example.com")
    answer(client, first, "a")
    ids["grace"] = become_staff(client, db, "grace@example.com")
    answer(client, first, "b")
    hints(client, first, 4)
    return ids


def rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_students_and_guests_cannot_use_it(client: TestClient, db: Session) -> None:
    register(client, "ada@example.com")
    for path in ("/api/staff/export/attempts.csv", "/api/staff/insights"):
        assert client.get(path).status_code == 403
    client.cookies.clear()
    assert client.get("/api/staff/export/hints.csv").status_code == 401


def test_attempts_csv_has_internal_ids_only_and_no_staff(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    response = client.get("/api/staff/export/attempts.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    assert "example.com" not in response.text
    assert "Ada" not in response.text

    attempts = rows(response.text)
    assert [(int(a["user_id"]), a["correct"]) for a in attempts] == [
        (ids["ada"], "False"),
        (ids["ada"], "True"),
        (ids["ada"], "True"),
        (ids["alan"], "True"),
    ]
    assert attempts[0]["submitted"] == '{"selected":"b"}'
    assert attempts[1]["hint_level"] == "3"


def test_hints_csv(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    hints_rows = rows(client.get("/api/staff/export/hints.csv").text)
    assert [(int(h["user_id"]), h["level"]) for h in hints_rows] == [
        (ids["ada"], "1"),
        (ids["ada"], "2"),
        (ids["ada"], "3"),
    ]


def test_unknown_tables_are_refused(client: TestClient, db: Session) -> None:
    become_staff(client, db, "grace@example.com")
    assert client.get("/api/staff/export/users.csv").status_code == 422


def test_a_cell_that_looks_like_a_formula_cannot_run(client: TestClient, db: Session) -> None:
    _, first, _ = make_video(db, first_title='=HYPERLINK("http://evil.example","x")')
    register(client, "ada@example.com")
    answer(client, first, "a")
    become_staff(client, db, "grace@example.com")
    (attempt,) = rows(client.get("/api/staff/export/attempts.csv").text)
    assert attempt["activity_title"].startswith("'=")


def test_insights_count_students_only(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    body = client.get("/api/staff/insights").json()
    assert (body["students"], body["attempts"], body["hintsViewed"]) == (2, 4, 3)

    first, second = body["activities"]  # most wrong attempts first
    assert first == {
        "id": ids["first"],
        "title": "Which leaves first?",
        "kind": "multiple_choice",
        "students": 2,
        "attempts": 3,
        "wrongAttempts": 1,
        "studentsPassed": 2,
        "studentsWithSupport": 1,
    }
    assert (second["id"], second["studentsPassed"], second["wrongAttempts"]) == (
        ids["second"],
        1,
        0,
    )

    (video,) = body["videos"]
    assert video["students"] == 2
    # Both passed the first checkpoint; only Ada the second: Alan stopped between them.
    assert [c["studentsPassed"] for c in video["checkpoints"]] == [2, 1]
    assert [c["atSeconds"] for c in video["checkpoints"]] == [20, 45]


def test_insights_before_the_pilot_are_empty(client: TestClient, db: Session) -> None:
    make_video(db)
    become_staff(client, db, "grace@example.com")
    body = client.get("/api/staff/insights").json()
    assert (body["students"], body["attempts"], body["activities"]) == (0, 0, [])
    assert [c["studentsPassed"] for c in body["videos"][0]["checkpoints"]] == [0, 0]
