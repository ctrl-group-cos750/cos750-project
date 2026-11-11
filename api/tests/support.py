"""Helpers several test files share."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, Module, ModuleProgress, User


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


def wrong_answer(activity: Activity) -> dict[str, Any]:
    """A real answer to the activity, using only what its config offers, that is wrong: the
    activity routes refuse an empty answer, or one naming things the activity doesn't have, with
    422 (app/services/submissions.py)."""
    config, solution = activity.config, activity.solution
    match activity.kind:
        case "multiple_choice":
            return {
                "selected": next(
                    o["id"] for o in config["options"] if o["id"] != solution["correct"]
                )
            }
        case "matching":
            rights = [r["id"] for r in config["right"]]
            return {"pairs": {
                left["id"]: next((r for r in rights if r != solution["pairs"].get(left["id"])), rights[0])
                for left in config["left"]
            }}  # fmt: skip
        case "parsons":
            order = list(solution["order"])
            flat = [i for item in order for i in (item if isinstance(item, list) else [item])]
            return {"order": flat[1:] + flat[:1]}  # every line one place off
        case "fix_the_bug":
            return {
                "order": [line["id"] for line in config["lines"]]
            }  # the faulty program as given
        case "fill_in":
            return {"answers": {
                str(blank): next(o for o in config["options"] if o != solution["answers"].get(str(blank), solution["answers"].get(blank)))
                for blank in config["blanks"]
            }}  # fmt: skip
        case "choose_tests":
            exposing = set(solution["exposing"])
            return {"selected": [t["id"] for t in config["tests"] if t["id"] not in exposing]}
        case "trace":
            start = config.get("start_vertex", config.get("startVertex"))
            other = next(v for v in config["vertices"] if v != start)
            return {
                "rows": [
                    {"visitedVertex": other, "queue": [], "visited": [other], "order": [other]}
                ]
            }
    raise AssertionError(f"no wrong answer for {activity.kind}")
