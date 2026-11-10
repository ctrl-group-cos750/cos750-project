"""The staff content editor (app/routers/staff_content.py): the fixtures seed the database, staff
edit it in the portal, the seed never writes over a staff edit, and every save is held to the
rules CI applies to the fixtures."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Hint, Segment, User, Video
from app.seed import PORTAL_IDS_FROM, load, read_fixtures

STAFF = {"email": "staff@example.com", "password": "Correct horse 1", "displayName": "Staff"}
STUDENT = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
BASE = "/api/staff/content"


def log_in(client: TestClient, db: Session, who: dict[str, str], staff: bool) -> None:
    assert client.post("/api/auth/register", json=who).status_code == 201
    if staff:
        user = db.scalar(select(User).where(User.email == who["email"]))
        assert user is not None
        user.is_staff = True
        db.commit()


@pytest.fixture
def staff(client: TestClient, db: Session) -> TestClient:
    load(db)  # the real fixtures, as a deploy seeds them
    log_in(client, db, STAFF, staff=True)
    return client


def activity_body(client: TestClient, activity_id: int) -> dict[str, Any]:
    """An activity as the editor sends it back: its GET without the read-only fields."""
    got = client.get(f"{BASE}/activities/{activity_id}")
    assert got.status_code == 200, got.text
    data: dict[str, Any] = got.json()
    for key in ("id", "edited", "inRepository", "inUse", "shownIn"):
        data.pop(key)
    return data


def module_body(client: TestClient, module_id: int) -> dict[str, Any]:
    got = client.get(f"{BASE}/modules/{module_id}")
    assert got.status_code == 200, got.text
    data: dict[str, Any] = got.json()
    for key in ("id", "edited", "inRepository", "segmentsEdited"):
        data.pop(key)
    return data


def test_only_staff_can_use_the_content_editor(client: TestClient, db: Session) -> None:
    assert client.get(BASE).status_code == 401
    log_in(client, db, STUDENT, staff=False)
    assert client.get(BASE).status_code == 403
    assert client.put(f"{BASE}/activities/311", json={}).status_code in (403, 422)


def test_the_overview_lists_the_seeded_content_as_from_the_repository(staff: TestClient) -> None:
    got = staff.get(BASE)
    assert got.status_code == 200, got.text
    data: dict[str, Any] = got.json()
    repo = read_fixtures()
    assert [o["id"] for o in data["objectives"]] == [o.id for o in repo.objectives]
    assert [m["id"] for m in data["modules"]] == [m.id for m in repo.modules]
    assert {a["id"] for a in data["activities"]} == {a.id for a in repo.activities}
    assert all(m["inRepository"] and not m["edited"] for m in data["modules"])


def test_an_edited_activity_survives_the_next_seed(staff: TestClient, db: Session) -> None:
    body = activity_body(staff, 311)
    body["title"] = "Edited in the portal"
    body["hints"] = [{"level": 1, "body": "A new first hint"}]
    saved = staff.put(f"{BASE}/activities/311", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["edited"] is True

    kept: list[str] = []
    load(db, kept=kept)  # the next deploy
    db.expire_all()
    assert db.get_one(Activity, 311).title == "Edited in the portal"
    assert [h.body for h in db.scalars(select(Hint).where(Hint.activity_id == 311))] == [
        "A new first hint"
    ]
    assert "activities 311" in kept
    # Everything nobody edited is still the repository's.
    assert db.get_one(Activity, 312).title == next(
        a.title for a in read_fixtures().activities if a.id == 312
    )


def test_an_invalid_activity_is_refused_and_nothing_changes(staff: TestClient, db: Session) -> None:
    body = activity_body(staff, 311)
    before = body["title"]
    body["title"] = "Should not stick"
    body["solution"] = {"correct": "no-such-option"}
    refused = staff.put(f"{BASE}/activities/311", json=body)
    assert refused.status_code == 422
    db.expire_all()
    assert db.get_one(Activity, 311).title == before
    assert db.get_one(Activity, 311).edited_at is None


def test_an_edit_that_breaks_a_cross_check_is_refused(staff: TestClient, db: Session) -> None:
    """A mastery item outside module 6 and the review paths: each item passes on its own, but
    the content as a whole does not, exactly as CI would refuse the same fixture."""
    body = activity_body(staff, 311)
    body["purpose"] = "mastery"
    refused = staff.put(f"{BASE}/activities/311", json=body)
    assert refused.status_code == 422
    assert "mastery item belongs in module 6" in refused.json()["detail"]
    db.expire_all()
    assert db.get_one(Activity, 311).purpose == "retrieval"


def test_a_module_s_segments_can_be_reordered_added_and_removed(
    staff: TestClient, db: Session
) -> None:
    body = module_body(staff, 3)
    segments = body["segments"]
    text = next(s for s in segments if s["kind"] == "text")
    segments.remove(text)
    segments.insert(0, text)  # moved to the front
    segments = [s for s in segments if s["kind"] != "worked_example"]  # one removed
    segments.append({"kind": "text", "title": "A new closing note", "body": "Well done."})
    body["segments"] = segments
    saved = staff.put(f"{BASE}/modules/3", json=body)
    assert saved.status_code == 200, saved.text
    out = saved.json()
    assert out["segmentsEdited"] is True
    assert out["edited"] is False  # its title and goals are still the repository's
    assert out["segments"][0]["id"] == text["id"]
    assert out["segments"][-1]["id"] >= PORTAL_IDS_FROM
    assert not any(s["kind"] == "worked_example" for s in out["segments"])

    kept: list[str] = []
    load(db, kept=kept)
    assert "segments of module 3" in kept
    assert module_body(staff, 3)["segments"] == [
        {k: v for k, v in s.items() if k != "id"} | {"id": s["id"]} for s in out["segments"]
    ]


def test_saving_a_module_unchanged_does_not_mark_it_edited(staff: TestClient) -> None:
    saved = staff.put(f"{BASE}/modules/3", json=module_body(staff, 3))
    assert saved.status_code == 200, saved.text
    assert saved.json()["edited"] is False
    assert saved.json()["segmentsEdited"] is False


def test_a_segment_from_another_module_is_refused(staff: TestClient) -> None:
    body = module_body(staff, 3)
    body["segments"][0]["id"] = module_body(staff, 1)["segments"][0]["id"]
    assert staff.put(f"{BASE}/modules/3", json=body).status_code == 422


def test_a_video_segment_chooses_its_video(staff: TestClient, db: Session) -> None:
    video = Video(
        title="Meet BFS",
        media_path="/media/videos/a.mp4",
        captions_path="/media/videos/a.vtt",
        transcript="",
        duration_seconds=60,
    )
    db.add(video)
    db.commit()
    body = module_body(staff, 3)
    first_video = next(s for s in body["segments"] if s["kind"] == "video")
    first_video["videoId"] = video.id
    saved = staff.put(f"{BASE}/modules/3", json=body)
    assert saved.status_code == 200, saved.text
    db.expire_all()
    assert db.get_one(Video, video.id).segment_id == first_video["id"]
    listed = staff.get(BASE).json()["videos"]
    assert listed == [{"id": video.id, "title": "Meet BFS", "segmentId": first_video["id"]}]

    # A text segment can't play a video.
    text = next(s for s in body["segments"] if s["kind"] == "text")
    text["videoId"] = video.id
    assert staff.put(f"{BASE}/modules/3", json=body).status_code == 422


def test_a_new_activity_gets_a_portal_id_and_an_unused_one_can_be_deleted(
    staff: TestClient, db: Session
) -> None:
    body = activity_body(staff, 311)
    body["title"] = "A new question"
    made = staff.post(f"{BASE}/activities", json=body)
    assert made.status_code == 201, made.text
    new_id = made.json()["id"]
    assert new_id >= PORTAL_IDS_FROM
    second = staff.post(f"{BASE}/activities", json=body).json()["id"]
    assert second == new_id + 1

    deleted = staff.delete(f"{BASE}/activities/{new_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True}
    assert db.get(Activity, new_id) is None


def test_deleting_a_repository_activity_only_takes_it_out_of_use(
    staff: TestClient, db: Session
) -> None:
    # 311 is shown by a segment: take it out of the module first.
    refused = staff.delete(f"{BASE}/activities/311")
    assert refused.status_code == 409
    body = module_body(staff, 3)
    body["segments"] = [s for s in body["segments"] if s.get("activityId") != 311]
    assert staff.put(f"{BASE}/modules/3", json=body).status_code == 200

    deleted = staff.delete(f"{BASE}/activities/311")
    assert deleted.json() == {"deleted": False}
    load(db)  # the next deploy does not bring it back into module 3
    db.expire_all()
    retired = db.get_one(Activity, 311)
    assert retired.module_id is None
    assert retired.visible is False


def test_a_checkpoint_question_is_edited_in_the_video_editor(
    staff: TestClient, db: Session
) -> None:
    video = Video(
        title="V", media_path="/m.mp4", captions_path="/m.vtt", transcript="", duration_seconds=5
    )
    question = Activity(kind="multiple_choice", title="Q", config={}, solution={})
    db.add_all([video, question])
    db.flush()
    db.add(Checkpoint(video_id=video.id, at_seconds=1, activity_id=question.id))
    db.commit()
    assert staff.get(f"{BASE}/activities/{question.id}").status_code == 409
    assert question.id not in {a["id"] for a in staff.get(BASE).json()["activities"]}


def test_use_the_repository_version_brings_the_fixture_back(staff: TestClient, db: Session) -> None:
    body = activity_body(staff, 311)
    original = body["title"]
    body["title"] = "Edited"
    assert staff.put(f"{BASE}/activities/311", json=body).status_code == 200
    back = staff.post(f"{BASE}/activities/311/use-repository")
    assert back.status_code == 204, back.text
    db.expire_all()
    assert db.get_one(Activity, 311).title == original
    assert db.get_one(Activity, 311).edited_at is None


def test_use_the_repository_version_needs_one_in_the_repository(staff: TestClient) -> None:
    made = staff.post(f"{BASE}/activities", json=activity_body(staff, 311)).json()
    refused = staff.post(f"{BASE}/activities/{made['id']}/use-repository")
    assert refused.status_code == 409


def test_an_objective_s_rule_change_is_kept_and_applied(staff: TestClient, db: Session) -> None:
    objective = staff.get(BASE).json()["objectives"][0]
    body = {k: objective[k] for k in ("text", "bloomLevel", "criterion")}
    body |= {"passFraction": None, "maxWrong": 0}
    saved = staff.put(f"{BASE}/objectives/{objective['id']}", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["maxWrong"] == 0
    both = body | {"passFraction": 0.5}
    assert staff.put(f"{BASE}/objectives/{objective['id']}", json=both).status_code == 422


def test_a_review_path_keeps_its_rules(staff: TestClient) -> None:
    path = staff.get(f"{BASE}/review-paths/1").json()
    segments = path["segments"]
    # Starting with an activity is refused: the path starts by teaching the objective again.
    refused = staff.put(f"{BASE}/review-paths/1", json={"segments": segments[1:]})
    assert refused.status_code == 422
    segments[0]["title"] = "Worked example, retitled"
    saved = staff.put(f"{BASE}/review-paths/1", json={"segments": segments})
    assert saved.status_code == 200, saved.text
    assert saved.json()["edited"] is True


def test_graphs_are_checked_by_the_bfs_engine(staff: TestClient) -> None:
    graph = {"name": "Tiny", "vertices": ["A", "B"], "edges": [{"source": "A", "target": "B"}]}
    assert staff.post(f"{BASE}/graphs", json=graph | {"startVertex": "Z"}).status_code == 422
    made = staff.post(f"{BASE}/graphs", json=graph | {"startVertex": "A"})
    assert made.status_code == 201, made.text
    assert made.json()["id"] >= PORTAL_IDS_FROM
    assert staff.delete(f"{BASE}/graphs/{made.json()['id']}").status_code == 204
    repo_graph = staff.get(BASE).json()["graphs"][0]["id"]
    assert staff.delete(f"{BASE}/graphs/{repo_graph}").status_code == 409


def test_a_module_made_in_the_portal_can_be_deleted_while_empty(staff: TestClient) -> None:
    module = {
        "slug": "extra-practice",
        "title": "Extra practice",
        "goals": ["Practise more BFS."],
        "estimatedMinutes": 10,
        "segments": [],
    }
    made = staff.post(f"{BASE}/modules", json=module)
    assert made.status_code == 201, made.text
    assert staff.post(f"{BASE}/modules", json=module).status_code == 422  # slug taken
    assert staff.delete(f"{BASE}/modules/{made.json()['id']}").status_code == 204
    assert staff.delete(f"{BASE}/modules/3").status_code == 409  # from the repository


def test_the_export_is_valid_fixtures_holding_the_portal_s_edits(
    staff: TestClient, tmp_path: Path, db: Session
) -> None:
    body = activity_body(staff, 311)
    body["title"] = "Edited for the export"
    assert staff.put(f"{BASE}/activities/311", json=body).status_code == 200
    db.add(User(email="x@example.com", display_name="X", password_hash="x"))  # noqa: S106
    db.commit()

    got = staff.get(f"{BASE}/export")
    assert got.status_code == 200
    assert got.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(got.content)) as archive:
        archive.extractall(tmp_path)
    exported = read_fixtures(tmp_path)  # what CI would run on the committed files
    assert next(a for a in exported.activities if a.id == 311).title == "Edited for the export"
    repo = read_fixtures()
    assert {a.id for a in exported.activities} == {a.id for a in repo.activities}
    assert len(exported.modules) == len(repo.modules)
    assert json.loads((tmp_path / "module-3.json").read_text())["modules"][0]["id"] == 3


def test_editing_a_mastery_item_keeps_earlier_attempts(staff: TestClient, db: Session) -> None:
    student = User(email="s@example.com", display_name="S", password_hash="x")  # noqa: S106
    db.add(student)
    db.flush()
    db.add(
        Attempt(user_id=student.id, activity_id=311, submitted={}, correct=True, score=1, detail={})
    )
    db.commit()
    body = activity_body(staff, 311)
    assert staff.get(f"{BASE}/activities/311").json()["inUse"] is True
    body["title"] = "Changed after an attempt"
    assert staff.put(f"{BASE}/activities/311", json=body).status_code == 200
    assert len(db.scalars(select(Attempt)).all()) == 1
    assert db.scalars(select(Segment).where(Segment.activity_id == 311)).first() is not None
