"""The content fixtures and their loader (app/seed). The first test is the CI gate the SE
document asks for (NFR-M5): an invalid fixture fails the build."""

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Hint, User, Video
from app.seed import load, read_fixtures


def test_every_committed_fixture_is_valid() -> None:
    content = read_fixtures()
    assert content.videos, "expected at least the placeholder video"


def write(folder: Path, data: dict[str, Any]) -> Path:
    (folder / "content.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


def activity(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "kind": "multiple_choice",
        "title": "Q",
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
        "hints": [{"level": 1, "body": "one"}, {"level": 2, "body": "two"}],
        **overrides,
    }


def video(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 1,
        "title": "V",
        "media_path": "/media/v.mp4",
        "captions_path": "/media/v.vtt",
        "transcript": "T",
        "duration_seconds": 60,
        "checkpoints": [{"id": 1, "at_seconds": 20, "activity_id": 1}],
        **overrides,
    }


@pytest.mark.parametrize(
    ("data", "problem"),
    [
        ({"activities": [activity(solution={"correct": "z"})]}, "not one of the options"),
        ({"activities": [activity(solution={"correct": "a", "feedback": {"q": "x"}})]}, "unknown"),
        ({"activities": [activity(kind="essay")]}, "kind"),
        ({"activities": [activity(config={"prompt": "Q", "options": []})]}, "options"),
        (
            {
                "activities": [
                    activity(hints=[{"level": 1, "body": "a"}, {"level": 1, "body": "b"}])
                ]
            },
            "share a level",
        ),
        ({"activities": [activity(hints=[{"level": 5, "body": "a"}])]}, "level"),
        ({"activities": [activity(), activity()]}, "used twice"),
        (
            {
                "activities": [activity()],
                "videos": [video(media_path="https://evil.example/x.mp4")],
            },
            "media_path",
        ),
        (
            {
                "activities": [activity()],
                "videos": [video(checkpoints=[{"id": 1, "at_seconds": 99, "activity_id": 1}])],
            },
            "after the end",
        ),
        ({"videos": [video()]}, "no fixture defines"),
        ({"activities": [activity(extra="x")]}, "extra"),
    ],
)
def test_invalid_fixtures_are_refused(tmp_path: Path, data: dict[str, Any], problem: str) -> None:
    with pytest.raises(ValueError, match=problem):
        read_fixtures(write(tmp_path, data))


def test_load_creates_content_and_a_rerun_updates_it_without_touching_attempts(
    tmp_path: Path, db: Session
) -> None:
    folder = write(tmp_path, {"activities": [activity()], "videos": [video()]})
    load(db, folder)
    user = User(email="ada@example.com", display_name="Ada", password_hash="not-a-real-hash")  # noqa: S106
    db.add(user)
    db.flush()
    db.add(
        Attempt(user_id=user.id, activity_id=1, submitted={}, correct=True, score=1.0, detail={})
    )
    db.commit()

    write(
        tmp_path,
        {
            "activities": [activity(title="Q2", hints=[{"level": 1, "body": "new"}])],
            "videos": [video(checkpoints=[{"id": 1, "at_seconds": 30, "activity_id": 1}])],
        },
    )
    load(db, folder)
    db.expire_all()
    assert db.get(Activity, 1).title == "Q2"  # type: ignore[union-attr]
    assert [h.body for h in db.scalars(select(Hint))] == ["new"]
    assert [c.at_seconds for c in db.scalars(select(Checkpoint))] == [30]
    assert len(db.scalars(select(Video)).all()) == 1
    assert len(db.scalars(select(Attempt)).all()) == 1


def test_a_bad_fixture_writes_nothing(tmp_path: Path, db: Session) -> None:
    folder = write(tmp_path, {"videos": [video()]})
    with pytest.raises(ValueError, match="no fixture defines"):
        load(db, folder)
    assert db.scalars(select(Video)).all() == []
