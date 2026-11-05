"""What the staff video editor sends and gets back (FR-3, FR-4). Unlike the student schemas,
these carry the answer and the feedback: only staff routes use them."""

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.schemas.activities import ChoiceOption
from app.schemas.base import ApiModel
from app.schemas.text import NoNul

MEDIA_PATH = r"^/media/videos/[A-Za-z0-9_-]+\.(mp4|vtt)$"
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1), NoNul]


class StaffHint(ApiModel):
    level: int = Field(ge=1, le=4)
    body: Annotated[Text, StringConstraints(max_length=5_000)]


class StaffQuestion(ApiModel):
    """A multiple-choice question. `feedback` says why each wrong option is wrong, by option id."""

    prompt: Annotated[Text, StringConstraints(max_length=5_000)]
    options: list[ChoiceOption] = Field(min_length=2, max_length=10)
    correct: str
    feedback: dict[str, Annotated[str, NoNul, StringConstraints(max_length=2_000)]] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def consistent(self) -> "StaffQuestion":
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)):
            raise ValueError("Two options share an id.")
        if self.correct not in ids:
            raise ValueError("Mark one of the options as correct.")
        if unknown := set(self.feedback) - set(ids):
            raise ValueError(f"Feedback for options that don't exist: {sorted(unknown)}")
        return self


class StaffCheckpointIn(ApiModel):
    """`id` is set for a checkpoint that already exists (it keeps its activity and the attempts
    on it) and left out for a new one."""

    id: int | None = None
    at_seconds: float = Field(ge=0)
    question: StaffQuestion
    hints: list[StaffHint] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def distinct_levels(self) -> "StaffCheckpointIn":
        levels = [hint.level for hint in self.hints]
        if len(levels) != len(set(levels)):
            raise ValueError("Two hints share a level.")
        return self


class StaffVideoIn(ApiModel):
    """A whole video as the editor saves it. PUT replaces the checkpoint list: a checkpoint left
    out is removed. Media paths come from `POST /api/staff/media` and must exist."""

    title: Annotated[Text, StringConstraints(max_length=200)]
    media_path: str = Field(pattern=MEDIA_PATH)
    captions_path: str = Field(pattern=MEDIA_PATH)
    transcript: Annotated[str, NoNul, StringConstraints(max_length=50_000)] = ""
    duration_seconds: int = Field(gt=0, le=4 * 3600)
    checkpoints: list[StaffCheckpointIn] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def consistent(self) -> "StaffVideoIn":
        if not self.media_path.endswith(".mp4"):
            raise ValueError("The video must be an .mp4 upload.")
        if not self.captions_path.endswith(".vtt"):
            raise ValueError("The captions must be a .vtt upload.")
        ids = [c.id for c in self.checkpoints if c.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("A checkpoint is listed twice.")
        for checkpoint in self.checkpoints:
            if checkpoint.at_seconds >= self.duration_seconds:
                raise ValueError(
                    f"A checkpoint at {checkpoint.at_seconds:g} s is after the end of the video."
                )
        return self


class StaffCheckpointOut(StaffCheckpointIn):
    id: int | None
    activity_id: int


class StaffVideoOut(StaffVideoIn):
    id: int
    checkpoints: list[StaffCheckpointOut]  # type: ignore[assignment]


class StaffVideoSummary(ApiModel):
    id: int
    title: str
    duration_seconds: int
    checkpoint_count: int


class MediaOut(ApiModel):
    """Where the upload is served from. Put it in a video's `mediaPath` or `captionsPath`."""

    path: str
    bytes: int
