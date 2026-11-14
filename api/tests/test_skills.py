"""The skill profile and module medals (FR-9.7, FR-9.8; #214): GET /api/me/skills, and the points
an answer reports earning."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import Attempt, HintView, ModuleProgress, UserBadge
from app.seed import load
from app.services.skills import backfill_practised, level_for, medal_for

STUDENT = {"email": "grace@example.com", "password": "Correct horse 1", "displayName": "Grace"}
RIGHT = {"submitted": {"selected": "a"}}
WRONG = {"submitted": {"selected": "b"}}


def mcq(id: int, objective: int | None, module: int | None, purpose: str = "practice") -> Any:
    return {
        "id": id,
        "kind": "multiple_choice",
        "title": f"Question {id}",
        "module_id": module,
        "objective_id": objective,
        "purpose": purpose,
        "config": {
            "prompt": "Q",
            "options": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        },
        "solution": {"correct": "a"},
        "hints": [{"level": n, "body": f"Hint {n}"} for n in (1, 2, 3, 4)],
    }


def segment(id: int, activity: int, **extra: Any) -> dict[str, Any]:
    return {"id": id, "kind": "activity", "title": f"Step {id}", "activity_id": activity} | extra


def course() -> dict[str, Any]:
    """Module 1 practises objective 1 on 101 to 104; 105 is support for objective 1 only shown
    to a student who struggles, so it isn't counted. Module 6 holds the mastery items."""
    return {
        "objectives": [
            {"id": 1, "text": "One", "bloom_level": "b", "criterion": "c", "pass_fraction": 1.0},
            {"id": 2, "text": "Two", "bloom_level": "b", "criterion": "c", "pass_fraction": 1.0},
        ],
        "modules": [
            {
                "id": 1,
                "slug": "m1",
                "title": "M1",
                "goals": ["g"],
                "estimated_minutes": 5,
                "segments": [
                    segment(1001, 101),
                    segment(1002, 102),
                    segment(1003, 103),
                    segment(1004, 104),
                    segment(1005, 105, support_for=1),
                ],
            },
            {
                "id": 6,
                "slug": "m6",
                "title": "M6",
                "goals": ["g"],
                "estimated_minutes": 5,
                "segments": [segment(6001, 601), segment(6002, 602)],
            },
        ],
        "activities": [
            mcq(101, 1, 1),
            mcq(102, 1, 1),
            mcq(103, 1, 1),
            mcq(104, 2, 1),
            mcq(105, 1, 1),
            mcq(601, 1, 6, "mastery"),
            mcq(602, 2, 6, "mastery"),
            *(mcq(1000 + 100 * o + n, o, None, p) for o in (1, 2) for n, p in REVIEW),
        ],
        "review_paths": [review_path(o) for o in (1, 2)],
    }


REVIEW = ((1, "review"), (2, "mastery"))


def review_path(objective: int) -> dict[str, Any]:
    """Every objective needs one once module 6 exists: practice, then a fresh item."""
    base = 1000 + 100 * objective
    return {
        "objective_id": objective,
        "segments": [
            {"id": base, "kind": "worked_example", "title": "Again", "body": "Like this."},
            segment(base + 1, base + 1),
            segment(base + 2, base + 2),
        ],
    }


@pytest.fixture
def loaded(tmp_path: Path, db: Session) -> None:
    (tmp_path / "course.json").write_text(json.dumps(course()), encoding="utf-8")
    load(db, tmp_path)


def log_in(client: TestClient) -> int:
    assert client.post("/api/auth/register", json=STUDENT).status_code == 201
    return int(client.get("/api/auth/me").json()["id"])


def answer(client: TestClient, activity: int, body: dict[str, Any] = RIGHT) -> dict[str, Any]:
    response = client.post(f"/api/activities/{activity}/attempts", json=body)
    assert response.status_code == 201, response.text
    return dict(response.json())


def see_hints(db: Session, user_id: int, activity: int, up_to: int) -> None:
    """Hints opened now: after the student's answers so far, as the hints route records them
    (`after_attempt`), so they count only against later answers (rewards.real_work)."""
    after = db.scalar(
        select(func.coalesce(func.max(Attempt.id), 0)).where(
            Attempt.user_id == user_id, Attempt.activity_id == activity
        )
    )
    for level in range(1, up_to + 1):
        db.add(
            HintView(user_id=user_id, activity_id=activity, level=level, after_attempt=after or 0)
        )
    db.commit()


def complete(db: Session, user_id: int, module_id: int) -> None:
    row = db.scalar(
        select(ModuleProgress).where(
            ModuleProgress.user_id == user_id, ModuleProgress.module_id == module_id
        )
    )
    if row is None:
        db.add(ModuleProgress(user_id=user_id, module_id=module_id, status="complete"))
    else:
        row.status = "complete"
    db.commit()


def profile(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/me/skills")
    assert response.status_code == 200
    return dict(response.json())


@pytest.mark.parametrize(
    ("first", "own", "tested_out", "medal"),
    [
        (4, 4, False, "gold"),
        (3, 4, False, "silver"),
        (0, 4, False, "silver"),
        (3, 3, False, "finished"),
        (0, 1, False, "finished"),
        # Every answer wrong (moved on after two tries): no medal, as no module points (#215).
        (0, 0, False, None),
        (0, 0, True, "silver"),  # tested out through the quick check
        (4, 4, True, "gold"),
    ],
)
def test_the_medal_rule(first: int, own: int, tested_out: bool, medal: str | None) -> None:
    assert medal_for(4, first, own, tested_out=tested_out) == medal


@pytest.mark.parametrize(
    ("answered", "own", "level"),
    [(0, 0, "not_started"), (2, 2, "practising"), (5, 3, "practising"), (5, 4, "secure")],
)
def test_the_practice_level(answered: int, own: int, level: str) -> None:
    assert level_for(answered, own, 5) == level


def test_the_profile_needs_a_login(client: TestClient, db: Session) -> None:
    assert client.get("/api/me/skills").status_code == 401


def test_practice_progress_counts_right_answers_per_objective(
    client: TestClient, loaded: None
) -> None:
    log_in(client)
    answer(client, 101)
    answer(client, 102, WRONG)
    skills = {s["id"]: s for s in profile(client)["objectives"]}
    # 105 is support only, and 601 is the mastery check: neither is practice anyone must meet.
    assert skills[1] | {"text": ""} == {
        "id": 1,
        "text": "",
        "answered": 2,
        "correct": 1,
        "onYourOwn": 1,
        "total": 3,
        "level": "practising",
        "result": None,
        # 102's wrong first attempt leaves at most 2 of 3 on your own: the mastery check (N1).
        "improve": {
            "kind": "check",
            "moduleId": 6,
            "segment": None,
            "objectiveId": None,
            "locked": False,
        },
        "modules": [1],
    }
    assert (skills[2]["level"], skills[2]["total"]) == ("not_started", 1)
    answer(client, 104)
    assert {s["id"]: s for s in profile(client)["objectives"]}[2]["level"] == "secure"


def test_the_result_appears_once_the_mastery_check_decides_it(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    complete(db, user, 1)
    answer(client, 601)
    assert {s["result"] for s in profile(client)["objectives"]} == {None}  # withheld (#144)
    answer(client, 602, WRONG)
    results = {s["id"]: s["result"] for s in profile(client)["objectives"]}
    assert results == {1: "met_independently", 2: "not_yet"}


def test_a_medal_needs_the_module_finished(client: TestClient, db: Session, loaded: None) -> None:
    user = log_in(client)
    answer(client, 101)
    answer(client, 102)
    medal = profile(client)["modules"][0]
    assert medal["moduleId"] == 1
    assert (medal["medal"], medal["headingFor"], medal["answered"]) == (None, "gold", 2)
    assert medal["objectives"] == [1, 2]
    answer(client, 103)
    answer(client, 104)
    complete(db, user, 1)
    assert profile(client)["modules"][0]["medal"] == "gold"


def test_a_wrong_first_answer_is_not_on_your_own(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Right after wrong is not real work (#222 review, A1): only the first attempt is evidence
    (FR-9.6), so one guessed item costs silver."""
    user = log_in(client)
    answer(client, 101, WRONG)
    answer(client, 101)
    answer(client, 102)
    answer(client, 103)
    answer(client, 104)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == ("finished", 3, 3)

    see_hints(db, user, 102, 4)
    # Already answered right without the hints, so it stays on your own: a medal never goes down.
    assert profile(client)["modules"][0]["medal"] == "finished"


def test_guessing_until_right_earns_no_silver_and_no_practised(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Wrong then right on every item of module 1 (two options each, so a guess): no silver, no
    Practised, and the objectives stay practising (#222 review, A1; the rule #221 uses for
    points)."""
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity, WRONG)
        answer(client, activity)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == (None, 0, 0)
    levels = {s["id"]: (s["level"], s["onYourOwn"]) for s in profile(client)["objectives"]}
    assert levels == {1: ("practising", 0), 2: ("practising", 0)}
    assert objective_badges(client) == {}


def test_a_restart_counts_for_the_profile_and_practised_but_not_the_medal(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Guessing wrong then right, restarting and answering right first time in the new round: the
    profile shows where the student stands now, so it is secure and Practised comes; the medal
    keeps the first attempt ever, so a restart can't win it back (#222 review by Koos; FR-9.6)."""
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity, WRONG)
        answer(client, activity)
    complete(db, user, 1)
    levels = {s["id"]: (s["level"], s["onYourOwn"]) for s in profile(client)["objectives"]}
    assert levels == {1: ("practising", 0), 2: ("practising", 0)}
    # Practice this round can't help: restart module 1, which is finished, gives new first answers.
    assert improve(client)[1] == {
        "kind": "restart",
        "moduleId": 1,
        "segment": None,
        "objectiveId": None,
        "locked": False,
    }
    assert client.post("/api/modules/1/restart").status_code == 200
    # Not redone yet: each item keeps the result it had.
    assert profile(client)["objectives"][0]["onYourOwn"] == 0
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    medal = next(m for m in profile(client)["modules"] if m["moduleId"] == 1)
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == (None, 0, 0)
    levels = {s["id"]: (s["level"], s["onYourOwn"]) for s in profile(client)["objectives"]}
    assert levels == {1: ("secure", 3), 2: ("secure", 1)}
    assert objective_badges(client) == {"lo1": "practised", "lo2": "practised"}


def test_only_the_first_answer_in_the_new_round_counts(
    client: TestClient, db: Session, loaded: None
) -> None:
    """A restart gives one new first answer, not a retry: wrong then right in the new round still
    isn't on your own, and hint 3 seen in the first round still counts against it (FR-2.8)."""
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    see_hints(db, user, 104, 3)
    complete(db, user, 1)
    assert client.post("/api/modules/1/restart").status_code == 200
    answer(client, 101, WRONG)
    answer(client, 101)
    answer(client, 104)  # after hint 3 from the first round
    own = {s["id"]: s["onYourOwn"] for s in profile(client)["objectives"]}
    assert own == {1: 2, 2: 0}  # 102 and 103 not redone keep theirs; 101 and 104 don't count


def test_gold_is_without_a_hint_and_silver_allows_hints_1_and_2(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Every answer right at the first attempt: gold without any hint; one after hint 2 makes it
    silver, still on your own, so Practised still comes."""
    user = log_in(client)
    see_hints(db, user, 101, 2)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == ("silver", 3, 4)
    assert objective_badges(client) == {"lo1": "practised", "lo2": "practised"}


def test_hint_3_before_the_only_right_answer_makes_it_finished(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    see_hints(db, user, 101, 3)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["onYourOwn"], medal["total"]) == ("finished", 3, 4)


def test_a_module_with_nothing_to_mark_has_no_medal(client: TestClient, loaded: None) -> None:
    log_in(client)
    assert [m["moduleId"] for m in profile(client)["modules"]] == [1]  # not module 6


def test_only_the_students_own(client: TestClient, db: Session, loaded: None) -> None:
    log_in(client)
    answer(client, 101)
    client.post("/api/auth/logout")
    other = STUDENT | {"email": "ada@example.com", "displayName": "Ada"}
    assert client.post("/api/auth/register", json=other).status_code == 201
    assert {s["correct"] for s in profile(client)["objectives"]} == {0}


def test_an_answer_says_what_points_it_earned(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    assert answer(client, 101)["points"] == 10
    assert answer(client, 101)["points"] == 0  # rewarded once
    assert answer(client, 103, WRONG)["points"] == 0
    assert answer(client, 103)["points"] == 0  # right only after a wrong first attempt (FR-9.1)
    see_hints(db, user, 102, 3)
    assert answer(client, 102)["points"] == 4


def test_a_mastery_check_answer_reports_no_points(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    complete(db, user, 1)
    assert answer(client, 601)["points"] == 0
    # The last answer finishes the check and gives its points, but still reports none (#144).
    assert answer(client, 602)["points"] == 0


def test_a_module_tested_out_through_its_quick_check_has_silver(
    client: TestClient, db: Session, loaded: None
) -> None:
    """A module passed by testing out (FR-8.2, #214) shows a medal like a finished one."""
    user = log_in(client)
    db.add(ModuleProgress(user_id=user, module_id=1, status="tested_out"))
    db.commit()
    medal = profile(client)["modules"][0]
    assert (medal["moduleId"], medal["complete"], medal["medal"]) == (1, True, "silver")


def test_a_wrong_guess_at_an_opening_puzzle_costs_no_medal(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Module 1 opens with a puzzle asked before any teaching, to show the student what they don't
    know yet (Malone and Lepper's curiosity). It is a diagnostic item, so a wrong guess there
    doesn't lose the module's gold for good, and the student can move on after one answer (review
    13 Nov, High 12)."""
    data = course()
    data["modules"][0]["segments"].insert(0, segment(1000, 106))
    data["activities"].append(mcq(106, None, 1, "diagnostic"))
    (tmp_path / "course.json").write_text(json.dumps(data), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    answer(client, 106, WRONG)
    assert profile(client)["modules"][0]["answered"] == 0  # the guess isn't counted
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    complete(db, user, 1)
    assert profile(client)["modules"][0]["medal"] == "gold"


def test_a_module_finished_before_its_medal_set_changed_keeps_its_medal(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Module 1's warm-up question left its medal set and a graph-words item joined it, so a
    student who finished module 1 with gold had answered 9 of the 10 items that now counted, and
    dropped to bronze (review of #223, Must fix 2). A finished module is judged on what the student
    was asked when they worked through it; a student who works through it now is asked the new
    item, and it counts for them."""
    (tmp_path / "course.json").write_text(json.dumps(course()), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    complete(db, user, 1)
    assert profile(client)["modules"][0]["medal"] == "gold"
    level = {s["id"]: s["level"] for s in profile(client)["objectives"]}

    # A new practice item with no objective (as 194) joins module 1, and 101 becomes a warm-up.
    data = course()
    data["modules"][0]["segments"].insert(4, segment(1006, 106))
    data["activities"].append(mcq(106, None, 1))
    next(a for a in data["activities"] if a["id"] == 101)["purpose"] = "diagnostic"
    next(a for a in data["activities"] if a["id"] == 101)["objective_id"] = None
    (tmp_path / "course.json").write_text(json.dumps(data), encoding="utf-8")
    load(db, tmp_path)
    db.expire_all()
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["total"]) == ("gold", 3, 3)
    assert {s["id"]: s["level"] for s in profile(client)["objectives"]} == level

    # Working through the module after the change, the new item is asked and counts.
    other = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
    client.post("/api/auth/logout")
    assert client.post("/api/auth/register", json=other).status_code == 201
    newcomer = int(client.get("/api/auth/me").json()["id"])
    for activity in (102, 103, 104):
        answer(client, activity)
    answer(client, 106, WRONG)
    answer(client, 106)
    complete(db, newcomer, 1)
    medal = profile(client)["modules"][0]
    # A right answer after a wrong one isn't real work (FR-9.6), so 106 is not on your own.
    assert (medal["medal"], medal["onYourOwn"], medal["total"]) == ("finished", 3, 4)


def test_going_back_to_an_item_that_joined_a_finished_module_never_lowers_its_medal(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """A gold student who opens module 1 again and gets the new item (as 194) wrong keeps gold:
    an activity first answered after the module was finished isn't one it was finished with, and
    more work never lowers a medal (review of #223, new finding 2)."""
    (tmp_path / "course.json").write_text(json.dumps(course()), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    # Finished an hour ago, a minute after these answers.
    for attempt in db.scalars(select(Attempt).where(Attempt.user_id == user)):
        attempt.created_at = datetime.now(tz=UTC) - timedelta(hours=1, minutes=1)
    db.add(
        ModuleProgress(
            user_id=user,
            module_id=1,
            status="complete",
            completed_at=datetime.now(tz=UTC) - timedelta(hours=1),
        )
    )
    db.commit()
    assert profile(client)["modules"][0]["medal"] == "gold"

    data = course()
    data["modules"][0]["segments"].insert(4, segment(1006, 106))
    data["activities"].append(mcq(106, None, 1))
    (tmp_path / "course.json").write_text(json.dumps(data), encoding="utf-8")
    load(db, tmp_path)
    db.expire_all()
    answer(client, 106, WRONG)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["total"]) == ("gold", 4, 4)
    # 106 was answered after the module was finished, so it isn't counted as answered either:
    # answered never exceeds total (review of #223, nit 4; it said 5 of 4).
    assert (medal["answered"], medal["total"]) == (4, 4)
    answer(client, 106)
    assert profile(client)["modules"][0]["medal"] == "gold"


def improve(client: TestClient) -> dict[int, Any]:
    return {s["id"]: s["improve"] for s in profile(client)["objectives"]}


def reach(db: Session, user_id: int, module_id: int, position: int) -> None:
    db.add(
        ModuleProgress(
            user_id=user_id,
            module_id=module_id,
            status="in_progress",
            current_segment_position=position,
        )
    )
    db.commit()


def test_each_objective_says_where_to_practise_it(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Not started or practising: the first module with an item still to do, at its segment when
    the student has reached it; never a segment further on, which can't be opened yet (#214)."""
    user = log_in(client)
    first = improve(client)
    assert first[1] == {
        "kind": "practise",
        "moduleId": 1,
        "segment": 0,
        "objectiveId": None,
        "locked": False,
    }
    assert first[2] == {
        "kind": "practise",
        "moduleId": 1,
        "segment": None,
        "objectiveId": None,
        "locked": False,
    }
    reach(db, user, 1, 3)
    answer(client, 101)
    # 102 (segment 1) is next for objective 1; 104 (segment 3) is reached for objective 2.
    assert improve(client)[1]["segment"] == 1
    assert improve(client)[2]["segment"] == 3
    # 102 wrong at the first attempt: it never counts again (FR-9.6), and 2 of 3 can't be 80%, so
    # practice can't make objective 1 secure. Not "practise in module 1" (it never could help),
    # but the mastery check, where it is still decided in full (#222 re-review, N1).
    answer(client, 102, WRONG)
    check = {"kind": "check", "moduleId": 6, "segment": None, "objectiveId": None, "locked": False}
    assert improve(client)[1] == check
    answer(client, 102)  # right after wrong, and 103 still to do: still the check
    assert improve(client)[1] == check
    answer(client, 103)
    assert improve(client)[1] == check
    level = {s["id"]: s["level"] for s in profile(client)["objectives"]}
    assert level[1] == "practising"


def test_practise_is_offered_while_secure_is_still_in_reach(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """Five practice items allow one wrong first attempt (4 of 5 is 80%): with one missed and some
    still to do, practice can still make it secure, so it still says where to practise."""
    data = course()
    module = data["modules"][0]
    module["segments"] = [segment(1000 + n, 100 + n) for n in range(1, 6)] + [segment(1009, 109)]
    data["activities"] = [a for a in data["activities"] if a["id"] not in (104, 105)] + [
        mcq(104, 1, 1),
        mcq(105, 1, 1),
        mcq(109, 2, 1),
    ]
    (tmp_path / "course.json").write_text(json.dumps(data), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    reach(db, user, 1, 5)
    answer(client, 101, WRONG)
    assert improve(client)[1] == {
        "kind": "practise",
        "moduleId": 1,
        "segment": 1,
        "objectiveId": None,
        "locked": False,
    }
    answer(client, 102, WRONG)  # two of five missed: 3 of 5 can't be 80%
    assert improve(client)[1]["kind"] == "check"


def test_secure_offers_a_revisit_and_gold_nothing(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    answer(client, 104)
    assert improve(client)[2] == {
        "kind": "revisit",
        "moduleId": 1,
        "segment": None,
        "objectiveId": None,
        "locked": False,
    }
    complete(db, user, 1)
    answer(client, 601)
    answer(client, 602, WRONG)
    after = improve(client)
    assert after[1] is None  # gold: met on your own
    # Not yet: its review path, the route after the mastery check (FR-7.5), never module 6.
    assert after[2] == {
        "kind": "review",
        "moduleId": None,
        "segment": None,
        "objectiveId": 2,
        "locked": False,
    }


def test_met_with_support_offers_a_revisit_not_a_review(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    complete(db, user, 1)
    see_hints(db, user, 601, 3)
    answer(client, 601)
    answer(client, 602)
    after = {s["id"]: s for s in profile(client)["objectives"]}
    assert after[1]["result"] == "met_with_support"
    assert after[1]["improve"] == {
        "kind": "revisit",
        "moduleId": 1,
        "segment": None,
        "objectiveId": None,
        "locked": False,
    }


# --- Badge levels: Practised when secure in practice (#214) -----------------------------------


def objective_badges(client: TestClient) -> dict[str, str | None]:
    return {
        b["badge"]: b["tier"]
        for b in client.get("/api/rewards").json()["badges"]
        if b["badge"].startswith("lo")
    }


def test_practised_comes_when_the_objective_is_secure_and_not_before(
    client: TestClient, loaded: None
) -> None:
    log_in(client)
    answer(client, 101)
    answer(client, 102)
    assert objective_badges(client) == {}  # practising: 2 of 3 answered
    points = client.get("/api/rewards").json()["points"]
    answer(client, 103)
    assert objective_badges(client) == {"lo1": "practised"}
    # The answer's own points only: Practised earns none.
    assert client.get("/api/rewards").json()["points"] == points + 10
    new = [b for b in client.get("/api/rewards").json()["badges"] if not b["seen"]]
    assert [(b["badge"], b["tier"]) for b in new] == [("lo1", "practised")]  # to announce


def test_practised_needs_80_percent_on_your_own(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Every item answered is not enough: 80% of them right without hint 3 or 4 (`level_for`).
    With three items, one answered after hint 3 keeps the objective practising."""
    user = log_in(client)
    answer(client, 101)
    answer(client, 102)
    see_hints(db, user, 103, 3)
    answer(client, 103)
    assert objective_badges(client) == {}  # 2 of 3 on your own: under 80%


def test_practised_is_given_once(client: TestClient, db: Session, loaded: None) -> None:
    user = log_in(client)
    answer(client, 104)
    answer(client, 104)
    answer(client, 104, WRONG)
    rows = db.scalars(select(UserBadge).where(UserBadge.user_id == user)).all()
    assert [(b.badge, b.tier) for b in rows] == [("lo2", "practised")]


def test_the_check_raises_practised_to_bronze_or_gold_and_not_yet_keeps_it(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    assert objective_badges(client) == {"lo1": "practised", "lo2": "practised"}
    client.post("/api/rewards/seen")
    complete(db, user, 1)
    see_hints(db, user, 601, 3)
    answer(client, 601)
    answer(client, 602, WRONG)
    assert objective_badges(client) == {"lo1": "bronze", "lo2": "practised"}
    upgraded = {b["badge"]: b for b in client.get("/api/rewards").json()["badges"]}["lo1"]
    assert upgraded["upgradedAt"] is not None
    assert not upgraded["seen"]  # announced: "now bronze"


def test_a_badge_already_gold_stays_gold_when_practice_becomes_secure(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    complete(db, user, 1)
    answer(client, 601)
    answer(client, 602)
    assert objective_badges(client) == {"lo1": "gold", "lo2": "gold"}
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    assert objective_badges(client) == {"lo1": "gold", "lo2": "gold"}


def test_the_seed_gives_practised_to_students_already_secure(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Students who were secure before badges had levels: their answers are in, the badge isn't."""
    user = log_in(client)
    for activity in (101, 102, 103):
        db.add(
            Attempt(
                user_id=user,
                activity_id=activity,
                submitted={},
                correct=True,
                score=1.0,
                detail={},
                hint_level=0,
            )
        )
    db.commit()
    assert objective_badges(client) == {}
    assert backfill_practised(db) == 1
    db.commit()
    assert objective_badges(client) == {"lo1": "practised"}
    assert backfill_practised(db) == 0  # safe to run on every seed


def test_each_objective_names_the_modules_that_practise_it(
    client: TestClient, loaded: None
) -> None:
    log_in(client)
    modules = {s["id"]: s["modules"] for s in profile(client)["objectives"]}
    assert modules == {1: [1], 2: [1]}  # not module 6: its items aren't practice


def test_hints_before_a_restart_still_count_for_the_medal(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Every hint opened on every item, the module finished, restarted, then every answer right:
    the hints gave those answers away, so no silver or gold (13 Nov review, as for points)."""
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        see_hints(db, user, activity, 4)
        answer(client, activity, WRONG)
    complete(db, user, 1)
    assert client.post("/api/modules/1/restart").status_code == 200
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    medal = next(m for m in profile(client)["modules"] if m["moduleId"] == 1)
    assert (medal["medal"], medal["onYourOwn"], medal["firstTime"]) == (None, 0, 0)
    assert objective_badges(client) == {}  # not secure in practice either: no Practised


def test_following_the_practise_it_in_list_earns_practised_on_the_real_content(
    db: Session,
) -> None:
    """The shelf's "Practise it in modules ..." (`modules`) names every module holding an item
    counted toward the objective, retrieval questions included, so answering right first time
    in exactly those modules makes every objective secure (#222 review, A3)."""
    from app.models import User
    from app.services import skills as skill_service

    load(db)
    user = User(email="ada@example.com", password_hash="x", display_name="Ada")  # noqa: S106
    db.add(user)
    db.flush()
    profile_now = skill_service.skills(db, user.id)
    items = skill_service._practice(db)
    places = skill_service._places(db, items)
    retrieval_elsewhere = False
    for skill in profile_now:
        mine = [a for a in items if a.objective_id == skill.objective_id]
        if not mine:
            continue
        counted = {places[a.id][1] for a in mine if a.id in places}
        assert set(skill.modules) == counted, skill.objective_id
        practice_only = {places[a.id][1] for a in mine if a.purpose == "practice"}
        retrieval_elsewhere |= counted != practice_only
    assert retrieval_elsewhere  # the real content has retrieval questions outside the practice

    listed = {s.objective_id: set(s.modules) for s in profile_now}
    for a in items:
        if a.objective_id is not None and places.get(a.id, (0, -1))[1] in listed[a.objective_id]:
            db.add(
                Attempt(
                    user_id=user.id,
                    activity_id=a.id,
                    submitted={},
                    correct=True,
                    score=1.0,
                    detail={},
                    hint_level=0,
                )
            )
    db.flush()
    with_items = {s.objective_id for s in profile_now if s.total > 0}
    assert skill_service.secure_objectives(db, user.id) == with_items


def test_the_mastery_check_is_named_not_linked_while_it_is_locked(
    client: TestClient, db: Session, tmp_path: Path
) -> None:
    """With a module between module 1 and the mastery check still to do, module 6 is locked, so
    the check is offered as where the objective will be shown, not as a link to a page that says
    it isn't open yet (#222 re-review, nit 3). Once the modules before it are done, it opens."""
    data = course()
    data["modules"].insert(
        1,
        {
            "id": 2,
            "slug": "m2",
            "title": "M2",
            "goals": ["g"],
            "estimated_minutes": 5,
            "segments": [segment(2001, 201)],
        },
    )
    data["activities"].append(mcq(201, 2, 2))
    (tmp_path / "course.json").write_text(json.dumps(data), encoding="utf-8")
    load(db, tmp_path)
    user = log_in(client)
    answer(client, 101)
    answer(client, 102, WRONG)  # objective 1 can no longer be secure: the check decides it
    assert improve(client)[1] == {
        "kind": "check",
        "moduleId": 6,
        "segment": None,
        "objectiveId": None,
        "locked": True,
    }
    complete(db, user, 1)
    complete(db, user, 2)
    assert improve(client)[1]["locked"] is False


def test_a_hint_before_a_right_first_answer_makes_it_silver(
    client: TestClient, db: Session, loaded: None
) -> None:
    user = log_in(client)
    see_hints(db, user, 101, 1)
    for activity in (101, 102, 103, 104):
        answer(client, activity)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == ("silver", 3, 4)


def test_a_right_answer_after_a_wrong_one_counts_for_no_medal(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Re-review of #221: wrong, wrong, then right earned no points or module points, but still
    silver, "secure" and on your own. The medal and the skill profile follow the evidence rule
    (FR-9.6), the same line as the module's points: only the first attempt counts."""
    user = log_in(client)
    answer(client, 101, WRONG)
    answer(client, 101)
    for activity in (102, 103):
        answer(client, activity)
    answer(client, 104, WRONG)
    answer(client, 104, WRONG)
    assert answer(client, 104)["points"] == 0
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["firstTime"], medal["onYourOwn"]) == ("finished", 2, 2)
    skills = {s["id"]: s for s in profile(client)["objectives"]}
    assert (skills[2]["correct"], skills[2]["onYourOwn"], skills[2]["level"]) == (
        1,
        0,
        "practising",
    )


def test_every_first_answer_wrong_earns_no_medal(
    client: TestClient, db: Session, loaded: None
) -> None:
    """Wrong then right everywhere: no module points (FR-9.1), so no medal either."""
    user = log_in(client)
    for activity in (101, 102, 103, 104):
        answer(client, activity, WRONG)
        answer(client, activity)
    complete(db, user, 1)
    medal = profile(client)["modules"][0]
    assert (medal["medal"], medal["onYourOwn"], medal["answered"]) == (None, 0, 4)


def queries_for_profile(client: TestClient, db: Session) -> int:
    statements: list[str] = []
    engine = db.get_bind()

    def count(*args: Any) -> None:
        statements.append(args[2])

    event.listen(engine, "before_cursor_execute", count)
    try:
        profile(client)
    finally:
        event.remove(engine, "before_cursor_execute", count)
    return len(statements)


def test_the_profile_costs_the_same_queries_however_much_was_answered(
    client: TestClient, db: Session, loaded: None
) -> None:
    """The evidence rule is one query (`rewards.first_answers`), not a few per answered item: at
    946ae95 the skills request ran 369 queries on the real seed (#221 re-review)."""
    user_id = log_in(client)
    answer(client, 101)
    one = queries_for_profile(client, db)
    see_hints(db, user_id, 102, 2)
    answer(client, 102)
    answer(client, 103, WRONG)
    answer(client, 103)
    answer(client, 104)
    assert queries_for_profile(client, db) == one
