import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import security
from app.passwords import RULES, password_problem

GRACE = {"email": "grace@example.com", "displayName": "Grace Hopper"}
MESSAGES = {rule.key: rule.message for rule in RULES}


@pytest.mark.parametrize(
    ("password", "broken"),
    [
        ("Ab1!", "length"),
        ("ABCDEF1!", "lower"),
        ("abcdef1!", "upper"),
        ("Abcdefg!", "number"),
        ("Abcdefg1", "symbol"),
    ],
)
def test_each_rule(password: str, broken: str) -> None:
    assert password_problem(password) == MESSAGES[broken]


@pytest.mark.parametrize(
    ("password", "email", "name"),
    [
        ("Grace-2024-x", "grace@example.com", ""),
        ("I am Hopper 1!", "x@example.com", "Grace Hopper"),
        ("My ada pw 9!", "ada@example.com", "Ada"),
    ],
    ids=["email name", "display name", "three-letter name"],
)
def test_your_own_name_or_email_is_refused(password: str, email: str, name: str) -> None:
    assert password_problem(password, email, name) == MESSAGES["personal"]


@pytest.mark.parametrize(
    "password",
    ["Correct horse 1", "Violet otter 41", "Tr0ub4dor&3", "Gr@phs-are-fun-9", "Äpfel und Birnen 7"],
)
def test_passwords_that_follow_the_rules_are_accepted(password: str) -> None:
    assert password_problem(password, "student@example.com", "Sam Student") is None


def test_a_space_counts_as_a_symbol() -> None:
    assert password_problem("Violet otter 41") is None


def test_the_first_broken_rule_is_reported() -> None:
    assert password_problem("abc") == MESSAGES["length"]


def test_register_explains_the_rule_on_the_password_field(client: TestClient, db: Session) -> None:
    res = client.post("/api/auth/register", json={**GRACE, "password": "violet otter 41"})
    assert res.status_code == 422
    assert res.json()["detail"] == [
        {"loc": ["body", "password"], "msg": MESSAGES["upper"], "type": "value_error"}
    ]


def test_register_refuses_the_students_own_name_as_a_password(
    client: TestClient, db: Session
) -> None:
    res = client.post("/api/auth/register", json={**GRACE, "password": "Hopper rocks 1"})
    assert res.json()["detail"][0]["msg"] == MESSAGES["personal"]


def test_an_existing_password_from_before_the_rules_still_logs_in(
    client: TestClient, db: Session
) -> None:
    from app.models import User

    db.add(
        User(
            email="old@example.com",
            display_name="Old",
            password_hash=security.hash_password("password1"),
        )
    )
    db.commit()
    res = client.post("/api/auth/login", json={"email": "old@example.com", "password": "password1"})
    assert res.status_code == 200


def test_at_most_four_passwords_are_hashed_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    running = peak = 0
    lock = threading.Lock()

    class SlowHasher:
        def verify(self, _password: str, _hash: str) -> bool:
            nonlocal running, peak
            with lock:
                running += 1
                peak = max(peak, running)
            time.sleep(0.05)
            with lock:
                running -= 1
            return False

    monkeypatch.setattr(security, "_password_hash", SlowHasher())
    threads = [
        threading.Thread(target=security.verify_password, args=("x", "h")) for _ in range(16)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == security.MAX_PARALLEL_HASHES
