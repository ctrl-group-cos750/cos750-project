"""Evaluation data for the pilot (GET /api/staff/export/{table}.csv and /api/staff/insights):
staff only, student accounts only, pseudonyms only (never the account id), and safe to open in a
spreadsheet."""

import csv
import io
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Hint, User, Video
from app.seed import load
from app.services.pseudonym import pseudonym

PASSWORD = "Correct horse 1"  # noqa: S105 (a test account)

# One objective, checked by one multiple-choice item in module 6, with its review path.
MASTERY_COURSE: dict[str, Any] = {
    "objectives": [
        {"id": 1, "text": "One", "bloom_level": "b", "criterion": "Right.", "pass_fraction": 1.0}
    ],
    "modules": [{"id": 6, "slug": "m6", "title": "M6", "goals": ["g"], "estimated_minutes": 5}],
    "activities": [
        {
            "id": aid,
            "kind": "multiple_choice",
            "title": f"Q{aid}",
            "module_id": module,
            "objective_id": 1,
            "purpose": purpose,
            "config": {
                "prompt": "Q",
                "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            },
            "solution": {"correct": "a"},
            "hints": [{"level": n, "body": f"h{n}"} for n in (1, 2, 3, 4)]
            if purpose == "review"
            else [],
        }
        for aid, module, purpose in (
            (601, 6, "mastery"),
            (1101, None, "review"),
            (1102, None, "mastery"),
        )
    ],
    "review_paths": [
        {
            "objective_id": 1,
            "segments": [
                {"id": 1100, "kind": "worked_example", "title": "Again", "body": "Like this."},
                {"id": 1101, "kind": "activity", "title": "Practice", "activity_id": 1101},
                {"id": 1102, "kind": "activity", "title": "Fresh", "activity_id": 1102},
            ],
        }
    ],
}


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


def become_demo(client: TestClient, db: Session, email: str) -> int:
    """A seeded demo account (app/seed/demo_accounts.py): its history is replayed, not real."""
    user_id = register(client, email)
    user = db.get(User, user_id)
    assert user is not None
    user.is_demo = True
    db.commit()
    return user_id


def event(client: TestClient, type: str, target_id: int) -> None:
    body = {"type": type, "targetId": target_id}
    assert client.post("/api/events", json=body).status_code == 204


def pilot(client: TestClient, db: Session) -> dict[str, int]:
    """Ada: starts the video, wrong, hints up to 3, right, then passes the second too. Alan: right
    first time on the first, then stops. Dee (a demo account) and Grace (staff) answer too, and
    must not be counted."""
    video, first, second = make_video(db)
    ids = {"video": video, "first": first, "second": second}
    ids["ada"] = register(client, "ada@example.com")
    event(client, "video_started", video)
    answer(client, first, "b")
    hints(client, first, 3)
    answer(client, first, "a")
    answer(client, second, "a")
    ids["alan"] = register(client, "alan@example.com")
    answer(client, first, "a")
    ids["dee"] = become_demo(client, db, "dee@example.com")
    event(client, "video_started", video)
    answer(client, first, "b")
    hints(client, first, 2)
    answer(client, second, "b")
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
    ada, alan = pseudonym(ids["ada"]), pseudonym(ids["alan"])
    assert [(a["student"], a["correct"]) for a in attempts] == [
        (ada, "False"),
        (ada, "True"),
        (ada, "True"),
        (alan, "True"),
    ]
    assert attempts[0]["submitted"] == '{"selected":"b"}'
    assert attempts[1]["hint_level"] == "3"


def test_hints_csv(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    hints_rows = rows(client.get("/api/staff/export/hints.csv").text)
    ada = pseudonym(ids["ada"])
    assert [(h["student"], h["level"]) for h in hints_rows] == [(ada, "1"), (ada, "2"), (ada, "3")]


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


def test_events_csv_is_the_students_timeline(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    events = rows(client.get("/api/staff/export/events.csv").text)
    ada = pseudonym(ids["ada"])
    assert [(e["student"], e["type"], e["ref"], e["payload"]) for e in events] == [
        (ada, "video_started", f"video:{ids['video']}", "{}"),
        (ada, "hint_shown", f"activity:{ids['first']}", '{"level":1}'),
        (ada, "hint_shown", f"activity:{ids['first']}", '{"level":2}'),
        (ada, "hint_shown", f"activity:{ids['first']}", '{"level":3}'),
    ]
    assert all(e["created_at"] for e in events)
    assert "example.com" not in client.get("/api/staff/export/events.csv").text


def test_objective_results_csv(client: TestClient, db: Session, tmp_path: Path) -> None:
    (tmp_path / "course.json").write_text(json.dumps(MASTERY_COURSE), encoding="utf-8")
    load(db, tmp_path)
    ada = register(client, "ada@example.com")
    answer(client, 601, "a")
    dee = become_demo(client, db, "dee@example.com")
    answer(client, 601, "a")
    become_staff(client, db, "grace@example.com")
    results = rows(client.get("/api/staff/export/objective_results.csv").text)
    assert [(r["student"], r["objective_id"], r["state"]) for r in results] == [
        (pseudonym(ada), "1", "met_independently")
    ]
    assert results[0]["evidence"].startswith("[")
    assert pseudonym(dee) not in [r["student"] for r in results]


def test_demo_accounts_are_not_pilot_students(client: TestClient, db: Session) -> None:
    ids = pilot(client, db)
    for table in ("attempts", "hints", "events"):
        users = {r["student"] for r in rows(client.get(f"/api/staff/export/{table}.csv").text)}
        assert pseudonym(ids["dee"]) not in users, table
        assert pseudonym(ids["grace"]) not in users, table


def test_students_are_pseudonyms_not_their_account_ids(client: TestClient, db: Session) -> None:
    """The account id is in /staff/accounts/<id>, so it would let anyone with staff access put a
    name to a row; the files carry a keyed hash instead, the same in every file (13 Nov audit)."""
    ids = pilot(client, db)
    files = {
        table: rows(client.get(f"/api/staff/export/{table}.csv").text)
        for table in ("attempts", "hints", "events")
    }
    for table, found in files.items():
        assert "user_id" not in found[0], table
        assert {r["student"] for r in found} <= {pseudonym(ids["ada"]), pseudonym(ids["alan"])}
        assert not any(r["student"].isdigit() for r in found), table
    assert pseudonym(ids["ada"]) != pseudonym(ids["alan"])
    assert pseudonym(ids["ada"]) != str(ids["ada"])


def test_insights_count_who_started_and_finished_a_video(client: TestClient, db: Session) -> None:
    """Bob starts the video and stops before the first checkpoint; Ada answers both checkpoints
    and watches to the end. Dee (demo) does the same as Ada and must not count."""
    video, first, second = make_video(db)
    register(client, "bob@example.com")
    event(client, "video_started", video)
    register(client, "ada@example.com")
    event(client, "video_started", video)
    answer(client, first, "a")
    answer(client, second, "a")
    event(client, "video_completed", video)
    become_demo(client, db, "dee@example.com")
    event(client, "video_started", video)
    answer(client, first, "a")
    event(client, "video_completed", video)
    become_staff(client, db, "grace@example.com")

    body = client.get("/api/staff/insights").json()
    assert body["students"] == 2  # Bob counts: he only started a video, but he was there
    (insight,) = body["videos"]
    assert (insight["students"], insight["finished"]) == (2, 1)
    assert [c["studentsPassed"] for c in insight["checkpoints"]] == [1, 1]


# --- Before the lecture: readiness and common wrong answers -------------------------------------


def readiness_course() -> dict[str, Any]:
    course: dict[str, Any] = json.loads(json.dumps(MASTERY_COURSE))
    for a in course["activities"]:
        a["solution"]["feedback"] = {"b": "Not quite: B is the one that leaves last."}
    return course


def test_readiness_counts_the_class_and_names_the_common_wrong_answer(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Ada meets the objective; Alan and Bea choose B. Dee (demo) and Grace (staff) don't count."""
    (tmp_path / "course.json").write_text(json.dumps(readiness_course()), encoding="utf-8")
    load(db, tmp_path)
    register(client, "ada@example.com")
    answer(client, 601, "a")
    register(client, "alan@example.com")
    answer(client, 601, "b")
    register(client, "bea@example.com")
    answer(client, 601, "b")
    become_demo(client, db, "dee@example.com")
    answer(client, 601, "b")
    become_staff(client, db, "grace@example.com")

    body = client.get("/api/staff/readiness").json()
    assert (body["students"], body["ready"]) == (3, 1)
    (objective,) = body["objectives"]
    assert (objective["metIndependently"], objective["metWithSupport"], objective["notYet"]) == (
        1,
        0,
        2,
    )
    (common,) = body["commonWrongAnswers"]
    assert common == {
        "activityId": 601,
        "title": "Q601",
        "objectiveId": 1,
        "answered": 3,
        "wrong": 2,
        "option": "B",
        "chosenBy": 2,
        "whyWrong": "Not quite: B is the one that leaves last.",
    }
    assert "example.com" not in json.dumps(body)


def test_readiness_is_for_staff_only(client: TestClient, db: Session) -> None:
    register(client, "ada@example.com")
    assert client.get("/api/staff/readiness").status_code == 403
    client.cookies.clear()
    assert client.get("/api/staff/readiness").status_code == 401


def test_objective_results_are_in_pseudonym_order_not_account_order(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Rows in account-id order would say who registered first (#215 review)."""
    (tmp_path / "course.json").write_text(json.dumps(MASTERY_COURSE), encoding="utf-8")
    load(db, tmp_path)
    ids = []
    for n in range(6):
        ids.append(register(client, f"student{n}@example.com"))
        answer(client, 601, "a")
    become_staff(client, db, "grace@example.com")
    students = [
        r["student"] for r in rows(client.get("/api/staff/export/objective_results.csv").text)
    ]
    assert sorted(set(students)) == sorted(pseudonym(i) for i in ids)
    assert students == sorted(students)
    assert students != [pseudonym(i) for i in ids]  # six in a row in id order would be chance
