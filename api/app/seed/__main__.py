"""`python -m app.seed`: load the content fixtures into the database at DATABASE_URL."""

from app.db import SessionLocal
from app.seed import load

with SessionLocal() as session:
    content = load(session)
print(
    f"seed: {len(content.activities)} activities, {len(content.graphs)} graphs, "
    f"{len(content.modules)} modules, "
    f"{sum(len(m.segments) for m in content.modules)} segments"
)
