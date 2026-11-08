"""The pilot's event log (FR-10.1, ID document §8): what each student did, with when.

Two kinds of event. The server logs the ones it decides (`SERVER_EVENTS`): a hint shown, an
objective's result changing. The browser reports the ones only it sees (`CLIENT_EVENTS`): a video
started or finished, a checkpoint reached, a segment viewed. Those come through
POST /api/events, which takes only these types, each about one kind of thing that must exist, and
no free text, so a student can't put anything else in the log. Attempts and hint views have their
own tables and exports; events are the timeline around them.

Every function adds to the session without committing, like the other services. Demo and staff
accounts are logged like anyone else and left out when the data is exported.
"""

from typing import Any, Literal, get_args

from sqlalchemy.orm import Session

from app.models import Checkpoint, Event, Segment, Video

ServerEvent = Literal["hint_shown", "result_changed"]
ClientEvent = Literal["video_started", "video_completed", "checkpoint_reached", "segment_viewed"]

SERVER_EVENTS: frozenset[str] = frozenset(get_args(ServerEvent))
CLIENT_EVENTS: frozenset[str] = frozenset(get_args(ClientEvent))
EVENT_TYPES = SERVER_EVENTS | CLIENT_EVENTS

# What each browser event is about: the kind of thing its `ref` names, and that thing's table.
CLIENT_REFS: dict[str, tuple[str, type[Video] | type[Checkpoint] | type[Segment]]] = {
    "video_started": ("video", Video),
    "video_completed": ("video", Video),
    "checkpoint_reached": ("checkpoint", Checkpoint),
    "segment_viewed": ("segment", Segment),
}


def log_event(
    session: Session, user_id: int, type: str, ref: str, payload: dict[str, Any] | None = None
) -> Event:
    """Add one event (not committed)."""
    if type not in EVENT_TYPES:
        raise ValueError(f"No event type {type!r}.")
    event = Event(user_id=user_id, type=type, ref=ref, payload=payload or {})
    session.add(event)
    return event


def log_client_event(session: Session, user_id: int, type: ClientEvent, target_id: int) -> Event:
    """A browser-reported event about the video, checkpoint or segment `target_id`. Raises
    LookupError if there is no such thing, so the log only ever names real content."""
    kind, model = CLIENT_REFS[type]
    if session.get(model, target_id) is None:
        raise LookupError(f"No {kind} {target_id}.")
    return log_event(session, user_id, type, f"{kind}:{target_id}")
