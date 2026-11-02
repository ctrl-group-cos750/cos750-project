import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import security
from app.passwords import (
    PERSONAL,
    REPETITIVE,
    TOO_COMMON,
    common_passwords,
    password_problem,
)

GRACE = {"email": "grace@example.com", "displayName": "Grace Hopper"}


def test_the_list_is_loaded() -> None:
    assert len(common_passwords()) == 10_001
    assert "password1" in common_passwords()


@pytest.mark.parametrize(
    "password",
    ["password1", "12345678", "PASSWORD1", "qwerty123", "iloveyou", "football", "welcome1"],
)
def test_common_passwords_are_refused(password: str) -> None:
    assert password_problem(password) == TOO_COMMON


@pytest.mark.parametrize("password", ["password123", "Dragon2024!", "football!!!", "monkey_99"])
def test_a_common_password_with_digits_or_symbols_added_is_refused(password: str) -> None:
    assert password_problem(password) == TOO_COMMON


@pytest.mark.parametrize(
    ("password", "email", "name"),
    [
        ("grace-2024-xyz", "grace@example.com", ""),
        ("I am hopper!!", "x@example.com", "Grace Hopper"),
        ("ctrl academy 1!", "x@example.com", ""),
        ("Ctrl-Academy-99", "x@example.com", ""),
        ("my cos212 pass", "x@example.com", ""),
    ],
    ids=["email name", "display name", "site name", "site name, dashes", "module code"],
)
def test_personal_and_site_words_are_refused(password: str, email: str, name: str) -> None:
    assert password_problem(password, email, name) == PERSONAL


@pytest.mark.parametrize("password", ["qqqqqqqqq", "abababab", "x9x9x9x9x", "!!!!!!!!!"])
def test_a_few_characters_repeated_are_refused(password: str) -> None:
    assert password_problem(password) == REPETITIVE


@pytest.mark.parametrize(
    "password",
    ["correct horse", "violet otter 42", "Tr0ub4dor&3x", "grap hs are fun", "ada-is-here-9"],
)
def test_ordinary_good_passwords_are_accepted(password: str) -> None:
    # "ada" is only three letters, too short to count as a personal word.
    assert password_problem(password, "ada@example.com", "Ada") is None


def test_register_explains_a_weak_password_on_the_field(client: TestClient, db: Session) -> None:
    res = client.post("/api/auth/register", json={**GRACE, "password": "password123"})
    assert res.status_code == 422
    assert res.json()["detail"] == [
        {"loc": ["body", "password"], "msg": TOO_COMMON, "type": "value_error"}
    ]


def test_register_refuses_the_students_own_name_as_a_password(
    client: TestClient, db: Session
) -> None:
    res = client.post("/api/auth/register", json={**GRACE, "password": "hopper rocks 1"})
    assert res.json()["detail"][0]["msg"] == PERSONAL


def test_an_existing_weak_password_still_logs_in(client: TestClient, db: Session) -> None:
    # The rules are for new passwords; nobody is locked out of an account made before them.
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
