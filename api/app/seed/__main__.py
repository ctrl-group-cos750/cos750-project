"""`python -m app.seed`: load the content fixtures into the database at DATABASE_URL, then the demo
accounts (app/seed/demo_accounts.py) if DEMO_PASSWORD is set."""

import os

from app.db import SessionLocal
from app.seed import load
from app.seed.demo_accounts import load_demo_accounts

with SessionLocal() as session:
    content = load(session)
    demo = load_demo_accounts(session, os.environ.get("DEMO_PASSWORD"))
print(
    f"seed: {len(content.activities)} activities, {len(content.graphs)} graphs, "
    f"{len(content.modules)} modules, "
    f"{sum(len(m.segments) for m in content.modules)} segments"
)
if demo:
    print(f"seed: demo accounts {', '.join(a.email for a in demo)}")
else:
    print("seed: no demo accounts (DEMO_PASSWORD is not set)")
