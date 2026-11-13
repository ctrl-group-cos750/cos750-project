"""The pilot's pseudonyms (FR-10.3, #215 review): keyed apart from the login key, and given to the
team by a command on the server, not shown in the staff portal."""

import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import pilot_name
from app.services import pseudonym as module


def test_a_pseudonym_is_keyed_on_its_own_key_not_the_login_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    try:
        monkeypatch.setenv("PILOT_PSEUDONYM_KEY", "pilot-key-one")
        first = importlib.reload(module).pseudonym(7)
        # Changing the login key (which logs everyone out) doesn't rename anyone.
        monkeypatch.setattr("app.security.SECRET_KEY", "a-new-login-key")
        assert importlib.reload(module).pseudonym(7) == first
        monkeypatch.setenv("PILOT_PSEUDONYM_KEY", "pilot-key-two")
        assert importlib.reload(module).pseudonym(7) != first
        assert first.startswith("s-")
    finally:
        monkeypatch.undo()
        importlib.reload(module)


def test_without_its_key_it_falls_back_to_the_login_key_with_a_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    try:
        monkeypatch.delenv("PILOT_PSEUDONYM_KEY", raising=False)
        with caplog.at_level("WARNING"):
            reloaded = importlib.reload(module)
        assert "PILOT_PSEUDONYM_KEY is not set" in caplog.text
        from app.security import SECRET_KEY

        assert reloaded.PSEUDONYM_KEY == SECRET_KEY
    finally:
        monkeypatch.undo()
        importlib.reload(module)


def test_the_command_gives_each_account_its_pseudonym(
    client: TestClient,
    db: Session,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = {"email": "ada@example.com", "password": "Correct horse 1", "displayName": "Ada"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    ada = int(client.get("/api/auth/me").json()["id"])
    assert pilot_name.pilot_names(db, ["Ada@Example.com", "nobody@example.com"]) == [
        ("Ada@Example.com", module.pseudonym(ada)),
        ("nobody@example.com", None),
    ]
    monkeypatch.setattr("app.db.SessionLocal", lambda: db)
    pilot_name.main(["ada@example.com", "nobody@example.com"])
    assert capsys.readouterr().out.splitlines() == [
        f"ada@example.com,{module.pseudonym(ada)}",
        "nobody@example.com,no such account",
    ]
