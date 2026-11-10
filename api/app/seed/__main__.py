"""`python -m app.seed`: load the content fixtures into the database at DATABASE_URL, then the demo
accounts (app/seed/demo_accounts.py) if DEMO_PASSWORD is set."""

import os

from app.db import SessionLocal
from app.seed import load
from app.seed.demo_accounts import load_demo_accounts

with SessionLocal() as session:
    kept: list[str] = []  # content staff edited in the portal, which the seed leaves alone
    content = load(
        session, kept=kept
    )  # broken content stops here, and so does the API (Dockerfile)
    notes: list[str] = []  # where a demo account's progress stopped short, and why
    try:
        demo = load_demo_accounts(session, os.environ.get("DEMO_PASSWORD"), notes=notes)
        demo_problem = None
    except ValueError as exc:
        # Demo accounts never stop the API: the previous ones are kept, and CI catches the same
        # problem in the PR that caused it (tests/test_demo_accounts.py).
        demo, demo_problem = [], str(exc)
segments = sum(len(m.segments) for m in content.modules)
print(
    f"seed: {len(content.objectives)} objectives, {len(content.modules)} modules, "
    f"{segments} segments, {len(content.review_paths)} review paths, "
    f"{len(content.activities)} activities, {len(content.graphs)} graphs"
)
if kept:
    print(f"seed: left as staff edited them in the portal: {', '.join(kept)}")
if demo_problem:
    print(f"seed: demo accounts NOT rebuilt, the previous ones are kept: {demo_problem}")
elif demo:
    print(f"seed: demo accounts {', '.join(a.email for a in demo)}")
    for note in notes:
        print(f"seed: demo progress {note}")
else:
    print("seed: no demo accounts (DEMO_PASSWORD is not set)")
