"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file holds `activities` (each with its `hints`) and `videos` (each with its
`checkpoints`), with fixed ids so a re-run updates the same rows. Re-running replaces content
only: students' attempts and hint views are never touched.

Every file is validated first, against the same schemas the checker uses, so a broken fixture
stops the load (and CI, see tests/test_seed.py) before anything is written.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models import Activity, Checkpoint, Hint, Video
from app.schemas.activities import (
    ActivityKind,
    FillInConfig,
    FillInSolution,
    MultipleChoiceConfig,
    MultipleChoiceSolution,
    ParsonsConfig,
    ParsonsSolution,
)

FIXTURES = Path(__file__).parent

# The config and solution schemas for each kind (FR-4.1). Add a kind here when its checker lands.
SHAPES: dict[str, tuple[type[BaseModel], type[BaseModel]]] = {
    "multiple_choice": (MultipleChoiceConfig, MultipleChoiceSolution),
    "parsons": (ParsonsConfig, ParsonsSolution),
    "fill_in": (FillInConfig, FillInSolution),
}


class HintFixture(BaseModel, extra="forbid"):
    level: int = Field(ge=1, le=4)
    body: str = Field(min_length=1)


class ActivityFixture(BaseModel, extra="forbid"):
    id: int
    kind: ActivityKind
    title: str = Field(max_length=200)
    visible: bool = True
    config: dict[str, Any]
    solution: dict[str, Any]
    hints: list[HintFixture] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def check_shapes(self) -> "ActivityFixture":
        config_shape, solution_shape = SHAPES[self.kind]
        config = config_shape.model_validate(self.config)
        solution = solution_shape.model_validate(self.solution)
        if isinstance(config, MultipleChoiceConfig) and isinstance(
            solution, MultipleChoiceSolution
        ):
            ids = {option.id for option in config.options}
            if solution.correct not in ids:
                raise ValueError(
                    f"activity {self.id}: correct option {solution.correct!r} is not one of the options"
                )
            if unknown := set(solution.feedback) - ids:
                raise ValueError(
                    f"activity {self.id}: feedback for unknown options {sorted(unknown)}"
                )
        levels = [hint.level for hint in self.hints]
        if len(levels) != len(set(levels)):
            raise ValueError(f"activity {self.id}: two hints share a level")
        return self


class CheckpointFixture(BaseModel, extra="forbid"):
    id: int
    at_seconds: float = Field(ge=0)
    activity_id: int


class VideoFixture(BaseModel, extra="forbid"):
    id: int
    title: str = Field(max_length=200)
    media_path: str = Field(pattern=r"^/media/[\w./-]+$", max_length=300)
    captions_path: str = Field(pattern=r"^/media/[\w./-]+\.vtt$", max_length=300)
    transcript: str
    duration_seconds: int = Field(gt=0)
    checkpoints: list[CheckpointFixture] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_checkpoints(self) -> "VideoFixture":
        for checkpoint in self.checkpoints:
            if checkpoint.at_seconds >= self.duration_seconds:
                raise ValueError(f"video {self.id}: checkpoint {checkpoint.id} is after the end")
        return self


class FixtureFile(BaseModel, extra="forbid"):
    activities: list[ActivityFixture] = Field(default_factory=list)
    videos: list[VideoFixture] = Field(default_factory=list)


def read_fixtures(folder: Path = FIXTURES) -> FixtureFile:
    """Every fixture file in `folder`, validated and merged. Raises ValueError naming the file and
    the problem if any file is invalid, or if ids clash or a checkpoint names a missing activity."""
    merged = FixtureFile()
    for path in sorted(folder.glob("*.json")):
        try:
            data = FixtureFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        merged.activities.extend(data.activities)
        merged.videos.extend(data.videos)
    for name, ids in (
        ("activity", [a.id for a in merged.activities]),
        ("video", [v.id for v in merged.videos]),
        ("checkpoint", [c.id for v in merged.videos for c in v.checkpoints]),
    ):
        if dupes := sorted({i for i in ids if ids.count(i) > 1}):
            raise ValueError(f"{name} ids used twice: {dupes}")
    activity_ids = {a.id for a in merged.activities}
    for video in merged.videos:
        for checkpoint in video.checkpoints:
            if checkpoint.activity_id not in activity_ids:
                raise ValueError(
                    f"video {video.id}: checkpoint {checkpoint.id} asks activity "
                    f"{checkpoint.activity_id}, which no fixture defines"
                )
    return merged


def load(session: Session, folder: Path = FIXTURES) -> FixtureFile:
    """Validate every fixture, then insert or update its rows in one transaction."""
    content = read_fixtures(folder)
    for a in content.activities:
        session.merge(
            Activity(
                id=a.id,
                kind=a.kind,
                title=a.title,
                visible=a.visible,
                config=a.config,
                solution=a.solution,
            )
        )
        session.flush()
        session.execute(delete(Hint).where(Hint.activity_id == a.id))
        session.add_all(Hint(activity_id=a.id, level=h.level, body=h.body) for h in a.hints)
    for v in content.videos:
        session.merge(
            Video(
                id=v.id,
                title=v.title,
                media_path=v.media_path,
                captions_path=v.captions_path,
                transcript=v.transcript,
                duration_seconds=v.duration_seconds,
            )
        )
        session.flush()
        session.execute(delete(Checkpoint).where(Checkpoint.video_id == v.id))
        session.add_all(
            Checkpoint(id=c.id, video_id=v.id, at_seconds=c.at_seconds, activity_id=c.activity_id)
            for c in v.checkpoints
        )
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        # Fixed ids don't move Postgres's id sequences; move them past the largest id, so a row
        # added without an id later doesn't collide with seeded content.
        for table in ("activities", "videos", "checkpoints"):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                    f"GREATEST((SELECT MAX(id) FROM {table}), 1))"
                )
            )
    session.commit()
    return content
