"""Loads content from the JSON fixtures in this folder (SE document §8 "Content is loaded from
fixtures", NFR-M5). Run it with `python -m app.seed`; the API container does on every start.

Each fixture file holds `activities`, each with its `hints`, with fixed ids so a re-run updates the
same rows. Re-running replaces content only: students' attempts and hint views are never touched.
Videos and their checkpoints are not fixtures: staff make them in the app's video editor, because
the media is uploaded to a volume, not committed (/staff/videos, app/routers/staff.py).

Every file is validated first, against the same schemas the checker uses, so a broken fixture
stops the load (and CI, see tests/test_seed.py) before anything is written.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.models import Activity, Hint
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


class FixtureFile(BaseModel, extra="forbid"):
    activities: list[ActivityFixture] = Field(default_factory=list)


def read_fixtures(folder: Path = FIXTURES) -> FixtureFile:
    """Every fixture file in `folder`, validated and merged. Raises ValueError naming the file and
    the problem if any file is invalid or if two activities share an id."""
    merged = FixtureFile()
    for path in sorted(folder.glob("*.json")):
        try:
            data = FixtureFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        merged.activities.extend(data.activities)
    ids = [a.id for a in merged.activities]
    if dupes := sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"activity ids used twice: {dupes}")
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
    session.flush()
    if session.get_bind().dialect.name == "postgresql":
        # Fixed ids don't move Postgres's id sequences; move them past the largest id, so a row
        # added without an id later doesn't collide with seeded content.
        for table in ("activities",):
            session.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "  # noqa: S608 (fixed names)
                    f"GREATEST((SELECT MAX(id) FROM {table}), 1))"
                )
            )
    session.commit()
    return content
