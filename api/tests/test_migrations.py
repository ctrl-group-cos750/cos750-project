from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

API_DIR = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.attributes["url"] = url
    return cfg


def test_migrations_apply_from_scratch_and_match_the_models(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")

    head = ScriptDirectory.from_config(cfg).get_current_head()
    with create_engine(url).connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == head

    # Fails when a model changed without a migration: run `alembic revision --autogenerate`.
    command.check(cfg)


def test_there_is_exactly_one_head() -> None:
    # Two heads means two branches each added a migration; merge them with `alembic merge heads`.
    heads = ScriptDirectory.from_config(alembic_config("sqlite://")).get_heads()
    assert len(heads) == 1
