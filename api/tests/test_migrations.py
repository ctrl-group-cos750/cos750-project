import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

API_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.attributes["url"] = url
    return cfg


def test_migrations_apply_from_scratch_and_match_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")

    head = ScriptDirectory.from_config(cfg).get_current_head()
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
    finally:
        engine.dispose()

    # Fails when a model changed without a migration: run `alembic revision --autogenerate`.
    command.check(cfg)


def test_there_is_exactly_one_head() -> None:
    # Two heads means two branches each added a migration; merge them with `alembic merge heads`.
    heads = ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()
    assert len(heads) == 1


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs TEST_DATABASE_URL (Postgres)")
def test_migrations_apply_on_postgres_and_match_the_models() -> None:
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = alembic_config(TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")  # every migration can be undone, too
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()
