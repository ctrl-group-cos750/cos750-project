import os

from sqlalchemy import create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://ctrl:ctrl@localhost:5432/ctrl"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
