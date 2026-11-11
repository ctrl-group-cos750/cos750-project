import os
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://ctrl:ctrl@localhost:5432/ctrl")

# FastAPI runs each request's code on a pool of 40 threads (anyio's default). A request keeps its
# database connection until its cleanup runs, and the cleanup needs a thread too. With fewer
# connections than threads (SQLAlchemy's default is 15), a burst of requests left every thread
# waiting for a connection that only a waiting thread could give back, and the API stalled for
# minutes (stress test, 2 Nov 2026). So the pool always has more connections than there are threads,
# and a request that still can't get one gives up after 10 s instead of 30.
REQUEST_THREADS = 40
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=REQUEST_THREADS + 10 - 20,
    pool_timeout=10,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Every model inherits from this. Import new models in app/models/__init__.py."""


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


# Use in a route as `session: DbSession`. Commit explicitly: `session.commit()`.
DbSession = Annotated[Session, Depends(get_session)]
