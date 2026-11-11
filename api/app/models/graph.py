from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class GraphScenario(Base):
    """One graph a student steps through in the BFS visualiser (SE document §8, FR-6).

    `vertices` is a list of labels; `edges` is a list of `{"source": ..., "target": ...}`. For an
    undirected scenario each edge counts both ways; for a directed one it goes source -> target.
    The BFS steps are not stored: they are computed on request by the one tested engine
    (app/services/bfs.py), so they always match what the lessons teach (FR-6.5).
    """

    __tablename__ = "graph_scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    directed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    vertices: Mapped[list[Any]] = mapped_column(JSON)
    edges: Mapped[list[Any]] = mapped_column(JSON)
    start_vertex: Mapped[str] = mapped_column(String(32))
    # Set when staff change it in the portal; the seed never writes over it then.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
