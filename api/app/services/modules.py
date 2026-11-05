"""Service functions for the module map and per-module progress (SE document §9, FR-2).

All functions take a SQLAlchemy ``Session`` and a ``user_id`` int — no FastAPI imports.
The router is responsible for calling ``session.commit()`` after any write (repo convention:
routers commit, services flush).

Status/unlock logic (FR-2.1):
- Module 0 is always at least ``open``.
- A module whose ``ModuleProgress.status`` is ``complete`` → ``complete``.
- A module whose ``ModuleProgress.status`` is ``in_progress`` → ``in_progress``.
- A module with no progress row: ``open`` if it is module 0 OR the previous module (by number)
  is ``complete``; otherwise ``locked``.

Custom exceptions:
- ``ModuleNotFound``  — raised when a module_id does not exist; router translates to 404.
- ``ModuleLocked``    — raised when a module's computed status is ``locked``; router → 403.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Module, ModuleProgress, Segment
from app.schemas.modules import ModuleDetailOut, ModuleOut, ModuleStatus, SegmentOut

# ---------------------------------------------------------------------------
# Domain errors (no FastAPI imports — router translates these to HTTP errors)
# ---------------------------------------------------------------------------


class ModuleNotFound(ValueError):
    """The requested module_id does not exist in the database."""


class ModuleLocked(ValueError):
    """The requested module's computed status is 'locked' for this student."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _segment_count(session: Session, module_id: int) -> int:
    """Count segments belonging to *module_id*."""
    result = session.scalar(select(func.count()).where(Segment.module_id == module_id))
    return result or 0


def _compute_status(
    progress: ModuleProgress | None,
    module_number: int,
    prev_complete: bool,
) -> ModuleStatus:
    """Compute the student-facing status for one module.

    Args:
        progress:      The ``ModuleProgress`` row for this user+module, or ``None``.
        module_number: The module's ``number`` field (0-based).
        prev_complete: Whether the immediately previous module (number - 1) is complete.

    Returns:
        One of ``"locked" | "open" | "in_progress" | "complete"``.
    """
    if progress is not None:
        # Trust whatever the progress row says — save_position sets it authoritatively.
        status: str = progress.status
        if status in ("complete", "in_progress", "open"):
            return status  # type: ignore[return-value]
    # No progress row (or an unknown status value) — derive from unlock rules (FR-2.1).
    if module_number == 0 or prev_complete:
        return "open"
    return "locked"


def _prev_module_complete(
    all_progress: dict[int, ModuleProgress],
    module_number: int,
    number_to_module_id: dict[int, int],
) -> bool:
    """Return True when module (module_number - 1) has status 'complete'.

    Args:
        all_progress:        Map of ``module_id → ModuleProgress`` for this user.
        module_number:       The module whose predecessor we are checking.
        number_to_module_id: Map of ``module.number → module.id``.
    """
    if module_number == 0:
        return False
    prev_module_id = number_to_module_id.get(module_number - 1)
    if prev_module_id is None:
        return False
    prev_progress = all_progress.get(prev_module_id)
    return prev_progress is not None and prev_progress.status == "complete"


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_modules_for_user(session: Session, user_id: int) -> list[ModuleOut]:
    """Return all modules ordered by ``position``, each with the student's computed status.

    Queries:
    1. All modules ordered by position.
    2. All ModuleProgress rows for this user (one round-trip, then resolved in Python).
    3. Segment counts per module (aggregated in one query).

    Args:
        session: SQLAlchemy session (no commit performed here).
        user_id: The authenticated student's id (NFR-S2, FR-1.3).

    Returns:
        A list of ``ModuleOut`` Pydantic objects, ordered by ``Module.position``.
    """
    modules = session.scalars(select(Module).order_by(Module.position)).all()

    # Bulk-fetch all progress rows for this user in one query.
    progress_rows = session.scalars(
        select(ModuleProgress).where(ModuleProgress.user_id == user_id)
    ).all()
    progress_by_module: dict[int, ModuleProgress] = {row.module_id: row for row in progress_rows}

    # Segment counts per module in one aggregated query.
    count_rows = session.execute(
        select(Segment.module_id, func.count().label("cnt"))
        .where(Segment.module_id.in_([m.id for m in modules]))
        .group_by(Segment.module_id)
    ).all()
    segment_counts: dict[int, int] = {row.module_id: row.cnt for row in count_rows}

    # Build a number → module_id lookup for the unlock rule.
    number_to_id: dict[int, int] = {m.number: m.id for m in modules}

    result: list[ModuleOut] = []
    for module in modules:
        prog = progress_by_module.get(module.id)
        prev_done = _prev_module_complete(progress_by_module, module.number, number_to_id)
        status = _compute_status(prog, module.number, prev_done)
        result.append(
            ModuleOut(
                id=module.id,
                number=module.number,
                slug=module.slug,
                title=module.title,
                goals=module.goals,
                estimated_minutes=module.estimated_minutes,
                status=status,
                segment_count=segment_counts.get(module.id, 0),
                current_segment_position=prog.current_segment_position if prog else 0,
            )
        )
    return result


def get_module_detail(session: Session, user_id: int, module_id: int) -> ModuleDetailOut:
    """Return a single module with its ordered segments and the student's computed status.

    Args:
        session:   SQLAlchemy session (no commit performed here).
        user_id:   The authenticated student's id (NFR-S2, FR-1.3).
        module_id: The surrogate id of the module to fetch.

    Raises:
        ModuleNotFound: The module does not exist.
        ModuleLocked:   The module's computed status is 'locked' for this student.

    Returns:
        A ``ModuleDetailOut`` Pydantic object with ``segments`` in position order.
    """
    module = session.get(Module, module_id)
    if module is None:
        raise ModuleNotFound(f"Module {module_id} not found.")

    # Fetch this user's progress row for this module (scoped to user_id — NFR-S2).
    prog = session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.module_id == module_id,
        )
    )

    # Determine whether the previous module is complete.
    prev_module_id: int | None = None
    prev_progress: ModuleProgress | None = None
    if module.number > 0:
        prev_module = session.scalar(select(Module).where(Module.number == module.number - 1))
        if prev_module is not None:
            prev_module_id = prev_module.id
            prev_progress = session.scalar(
                select(ModuleProgress).where(
                    ModuleProgress.user_id == user_id,
                    ModuleProgress.module_id == prev_module_id,
                )
            )
    prev_done = prev_progress is not None and prev_progress.status == "complete"

    status = _compute_status(prog, module.number, prev_done)

    if status == "locked":
        raise ModuleLocked(f"Module {module_id} is locked for user {user_id}.")

    # Segments in position order.
    segments = session.scalars(
        select(Segment).where(Segment.module_id == module_id).order_by(Segment.position)
    ).all()

    segment_count = len(segments)

    return ModuleDetailOut(
        id=module.id,
        number=module.number,
        slug=module.slug,
        title=module.title,
        goals=module.goals,
        estimated_minutes=module.estimated_minutes,
        status=status,
        segment_count=segment_count,
        current_segment_position=prog.current_segment_position if prog else 0,
        segments=[
            SegmentOut(
                id=seg.id,
                position=seg.position,
                kind=seg.kind,  # type: ignore[arg-type]
                title=seg.title,
                body=seg.body,
                video_id=seg.video_id,
                activity_id=seg.activity_id,
            )
            for seg in segments
        ],
    )


def save_position(
    session: Session, user_id: int, module_id: int, segment_position: int
) -> ModuleProgress:
    """Upsert the student's current segment position and update the module status.

    Creates or updates the ``ModuleProgress`` row (honouring the
    ``UniqueConstraint(user_id, module_id)``).

    Status transitions:
    - Sets ``status = 'in_progress'`` unless the student has reached or passed the last
      segment index (``segment_position >= segment_count - 1``), in which case
      ``status = 'complete'`` and ``completed_at`` is recorded.

    # TODO (future activity story): Gate completion on required activities being passed.
    #   When activity-gating is implemented, only set status='complete' here if
    #   all required Activity rows linked to this module's segments are answered
    #   correctly by this user. Until then, reaching the last segment is sufficient
    #   (approved decision 3).

    Does NOT call ``session.commit()``; the router is responsible for committing
    (repo convention).

    Args:
        session:          SQLAlchemy session.
        user_id:          The authenticated student's id (NFR-S2, FR-1.3).
        module_id:        The surrogate id of the module.
        segment_position: Zero-based position of the segment the student just reached.

    Raises:
        ModuleNotFound: The module does not exist.
        ModuleLocked:   The module is locked for this student.

    Returns:
        The created or updated ``ModuleProgress`` ORM object (not yet committed).
    """
    module = session.get(Module, module_id)
    if module is None:
        raise ModuleNotFound(f"Module {module_id} not found.")

    # Fetch existing progress row (scoped to user_id — NFR-S2).
    prog = session.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id,
            ModuleProgress.module_id == module_id,
        )
    )

    # Determine whether this module is unlocked for the student.
    prev_done = False
    if module.number > 0:
        prev_module = session.scalar(select(Module).where(Module.number == module.number - 1))
        if prev_module is not None:
            prev_progress = session.scalar(
                select(ModuleProgress).where(
                    ModuleProgress.user_id == user_id,
                    ModuleProgress.module_id == prev_module.id,
                )
            )
            prev_done = prev_progress is not None and prev_progress.status == "complete"

    current_status = _compute_status(prog, module.number, prev_done)
    if current_status == "locked":
        raise ModuleLocked(f"Module {module_id} is locked for user {user_id}.")

    # How many segments does this module have?
    segment_count = _segment_count(session, module_id)
    last_index = max(segment_count - 1, 0)

    # Determine new status and whether to record completion.
    # TODO (future activity story): Gate completion on required activities being passed.
    #   Replace the line below with a check that all required activities on this module's
    #   segments are correctly answered before setting status='complete'. See approved decision 3.
    is_complete = segment_count > 0 and segment_position >= last_index

    if prog is None:
        # Create a new progress row.
        prog = ModuleProgress(
            user_id=user_id,
            module_id=module_id,
            current_segment_position=segment_position,
            status="complete" if is_complete else "in_progress",
            completed_at=datetime.now(tz=UTC) if is_complete else None,
        )
        session.add(prog)
    else:
        # Update the existing row in-place.
        prog.current_segment_position = segment_position
        prog.status = "complete" if is_complete else "in_progress"
        if is_complete and prog.completed_at is None:
            # Record the first time the module was completed; do not overwrite a prior timestamp.
            prog.completed_at = datetime.now(tz=UTC)

    # Flush so the caller's session reflects the change; router commits.
    session.flush()
    return prog
