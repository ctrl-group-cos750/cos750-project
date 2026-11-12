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


def test_0016_keeps_each_hint_level_s_first_view(tmp_path: Path) -> None:
    """Hint views recorded twice by requests at the same moment (#138) are removed, keeping the
    earliest, so the unique constraint can be added to a database that already has them."""
    url = f"sqlite:///{tmp_path / 'hints.db'}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0015")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, display_name, password_hash)"
                    " VALUES (1, 'ada@example.com', 'Ada', 'x')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO activities (id, kind, title, config, solution)"
                    " VALUES (1, 'multiple_choice', 'Q', '{}', '{}')"
                )
            )
            for view_id, level in ((1, 1), (2, 1), (3, 2), (4, 1), (5, 2)):
                conn.execute(
                    text(
                        "INSERT INTO hint_views (id, user_id, activity_id, level)"
                        " VALUES (:id, 1, 1, :level)"
                    ),
                    {"id": view_id, "level": level},
                )
        command.upgrade(cfg, "0016")
        with engine.connect() as conn:
            kept = conn.execute(text("SELECT id, level FROM hint_views ORDER BY id")).all()
        assert [tuple(row) for row in kept] == [(1, 1), (3, 2)]
    finally:
        engine.dispose()


def test_0017_upgrades_a_staging_database_without_moving_anyone(tmp_path: Path) -> None:
    """A database built on staging (at 0016) keeps its segments and every student's place: no
    segment becomes support and nothing is recorded as shown until the fixtures say so (#172)."""
    url = f"sqlite:///{tmp_path / 'support.db'}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0016")
    engine = create_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, email, display_name, password_hash)"
                    " VALUES (1, 'ada@example.com', 'Ada', 'x')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO modules (id, slug, title, goals, estimated_minutes, position)"
                    " VALUES (2, 'graphs', 'Graphs', '[]', 10, 2)"
                )
            )
            for segment_id, position in ((201, 0), (202, 1), (203, 2)):
                conn.execute(
                    text(
                        "INSERT INTO segments (id, module_id, position, kind, title, body)"
                        " VALUES (:id, 2, :position, 'text', 'S', '')"
                    ),
                    {"id": segment_id, "position": position},
                )
            conn.execute(
                text(
                    "INSERT INTO module_progress (user_id, module_id, status,"
                    " current_segment_position) VALUES (1, 2, 'in_progress', 1)"
                )
            )
        command.upgrade(cfg, "0017")
        with engine.connect() as conn:
            segments = conn.execute(
                text("SELECT id, position, support_for FROM segments ORDER BY id")
            ).all()
            place = conn.execute(
                text("SELECT current_segment_position, status FROM module_progress")
            ).one()
            shown = conn.execute(text("SELECT COUNT(*) FROM shown_segments")).scalar()
        assert [tuple(row) for row in segments] == [(201, 0, None), (202, 1, None), (203, 2, None)]
        assert tuple(place) == (1, "in_progress")
        assert shown == 0
        command.downgrade(cfg, "0016")  # and it can be undone
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM segments")).scalar() == 3
    finally:
        engine.dispose()
