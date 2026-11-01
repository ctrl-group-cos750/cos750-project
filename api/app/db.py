import os
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://ctrl:ctrl@localhost:5432/ctrl")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every model inherits from this. Import new models in app/models/__init__.py."""


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


# Use in a route as `session: DbSession`. Commit explicitly: `session.commit()`.
DbSession = Annotated[Session, Depends(get_session)]
