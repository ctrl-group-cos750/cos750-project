"""Helpers several test files share."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Module, ModuleProgress, User


def open_module(db: Session) -> int:
    """The id of a module every student may open: the course's first, made if there is none. An
    activity is only usable inside the course (app/services/access.py), so a test activity that
    isn't about where it sits goes here."""
    first = db.scalar(select(Module).order_by(Module.position).limit(1))
    if first is None:
        first = Module(id=0, slug="m0", title="Start", goals=[], estimated_minutes=5, position=0)
        db.add(first)
        db.commit()
    return first.id


def complete_modules_before(db: Session, email: str, module_id: int) -> None:
    """Mark every module before `module_id` complete for this student, as if they had worked
    through them, so `module_id` opens."""
    user = db.scalars(select(User).where(User.email == email)).one()
    target = db.get_one(Module, module_id)
    for module in db.scalars(select(Module).where(Module.position < target.position)):
        db.add(ModuleProgress(user_id=user.id, module_id=module.id, status="complete"))
    db.commit()
