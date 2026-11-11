"""Saving a video and its checkpoints from the staff editor. Each checkpoint asks a
multiple-choice activity with its own hints; the editor treats the three as one thing."""

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models import Activity, Attempt, Checkpoint, Hint, HintView, Video
from app.schemas.staff import (
    StaffCheckpointIn,
    StaffCheckpointOut,
    StaffHint,
    StaffQuestion,
    StaffVideoIn,
    StaffVideoOut,
)


class UnknownCheckpoint(ValueError):
    pass


def _activity_fields(video_title: str, checkpoint: StaffCheckpointIn) -> dict[str, object]:
    q = checkpoint.question
    minutes, seconds = divmod(int(checkpoint.at_seconds), 60)
    return {
        "kind": "multiple_choice",
        "title": f"{video_title} at {minutes}:{seconds:02d}"[:200],
        "visible": True,
        "config": {"prompt": q.prompt, "options": [o.model_dump() for o in q.options]},
        "solution": {"correct": q.correct, "feedback": q.feedback},
    }


def _in_use(session: Session, activity_id: int) -> bool:
    return bool(
        session.scalar(select(exists().where(Attempt.activity_id == activity_id)))
        or session.scalar(select(exists().where(HintView.activity_id == activity_id)))
    )


def save_video(session: Session, video: Video, data: StaffVideoIn) -> None:
    """Apply the editor's whole video to `video` (new or existing) and commit.

    A checkpoint with an `id` keeps its activity, so attempts already made on it stay linked. A
    checkpoint the editor left out is removed; its activity goes too unless students have answered
    it or seen its hints, in which case it is kept for the evaluation data (FR-10)."""
    video.title = data.title
    video.media_path = data.media_path
    video.captions_path = data.captions_path
    video.transcript = data.transcript
    video.duration_seconds = data.duration_seconds
    session.add(video)
    session.flush()

    existing = {
        c.id: c for c in session.scalars(select(Checkpoint).where(Checkpoint.video_id == video.id))
    }
    if unknown := {c.id for c in data.checkpoints if c.id is not None} - set(existing):
        raise UnknownCheckpoint(f"Checkpoints {sorted(unknown)} are not on this video.")

    kept = {c.id for c in data.checkpoints if c.id is not None}
    for checkpoint_id, checkpoint in existing.items():
        if checkpoint_id not in kept:
            activity_id = checkpoint.activity_id
            session.delete(checkpoint)
            session.flush()
            if not _in_use(session, activity_id):
                session.execute(delete(Hint).where(Hint.activity_id == activity_id))
                session.execute(delete(Activity).where(Activity.id == activity_id))

    for incoming in data.checkpoints:
        fields = _activity_fields(data.title, incoming)
        if incoming.id is None:
            activity = Activity(**fields)
            session.add(activity)
            session.flush()
            session.add(
                Checkpoint(
                    video_id=video.id, at_seconds=incoming.at_seconds, activity_id=activity.id
                )
            )
        else:
            checkpoint = existing[incoming.id]
            checkpoint.at_seconds = incoming.at_seconds
            activity = session.get_one(Activity, checkpoint.activity_id)
            for key, value in fields.items():
                setattr(activity, key, value)
        session.execute(delete(Hint).where(Hint.activity_id == activity.id))
        session.add_all(
            Hint(activity_id=activity.id, level=h.level, body=h.body) for h in incoming.hints
        )
    session.commit()


def video_for_editor(session: Session, video: Video) -> StaffVideoOut:
    """The video as the editor shows it, answers and feedback included."""
    rows = session.execute(
        select(Checkpoint, Activity)
        .join(Activity, Activity.id == Checkpoint.activity_id)
        .where(Checkpoint.video_id == video.id)
        .order_by(Checkpoint.at_seconds, Checkpoint.id)
    ).all()
    checkpoints = []
    for checkpoint, activity in rows:
        hints = session.scalars(
            select(Hint).where(Hint.activity_id == activity.id).order_by(Hint.level)
        )
        checkpoints.append(
            StaffCheckpointOut(
                id=checkpoint.id,
                at_seconds=checkpoint.at_seconds,
                activity_id=activity.id,
                question=StaffQuestion(
                    prompt=activity.config["prompt"],
                    options=activity.config["options"],
                    correct=activity.solution["correct"],
                    feedback=activity.solution.get("feedback", {}),
                ),
                hints=[StaffHint(level=h.level, body=h.body) for h in hints],
            )
        )
    return StaffVideoOut(
        id=video.id,
        title=video.title,
        media_path=video.media_path,
        captions_path=video.captions_path,
        transcript=video.transcript,
        duration_seconds=video.duration_seconds,
        checkpoints=checkpoints,
    )
