"""`python -m app.seed`: load the content fixtures into the database at DATABASE_URL, then the demo
accounts (app/seed/demo_accounts.py) if DEMO_PASSWORD is set.

`python -m app.seed --check`: check the fixtures and the authoring templates (app/seed/templates)
with the rules CI applies (tests/test_seed.py), and touch no database. See app/seed/README.md."""

import os
import sys

from app.db import SessionLocal
from app.seed import load, read_fixtures, read_templates
from app.seed.demo_accounts import load_demo_accounts
from app.services.modules import backfill_module_rewards
from app.services.skills import backfill_practised

if sys.argv[1:] == ["--check"]:
    try:
        checked = read_fixtures()
        templates = read_templates()
    except ValueError as exc:
        sys.exit(f"seed --check: FAILED\n{exc}")
    print(
        f"seed --check: fixtures valid ({len(checked.modules)} modules, "
        f"{len(checked.activities)} activities, {len(checked.review_paths)} review paths, "
        f"{len(checked.graphs)} graphs); templates valid ({', '.join(templates)})"
    )
    sys.exit(0)

with SessionLocal() as session:
    kept: list[str] = []  # content staff edited in the portal, which the seed leaves alone
    caught_up: list[str] = []  # staff edits the repository now holds, so it decides again
    problems: list[str] = []  # the repository's content and the portal's edits don't fit together
    # Broken fixtures stop here, and so does the API (Dockerfile). Content that is only broken in
    # combination with a staff edit does not: staff fix it in the portal, which needs the API.
    content = load(session, kept=kept, caught_up=caught_up, problems=problems)
    notes: list[str] = []  # where a demo account's progress stopped short, and why
    try:
        demo = load_demo_accounts(session, os.environ.get("DEMO_PASSWORD"), notes=notes)
        demo_problem = None
    except ValueError as exc:
        # Demo accounts never stop the API: the previous ones are kept, and CI catches the same
        # problem in the PR that caused it (tests/test_demo_accounts.py).
        demo, demo_problem = [], str(exc)
    # Modules completed before module points were awarded get them now, if earned (#166).
    backfilled = backfill_module_rewards(session)
    # Students secure in practice before objective badges had levels get Practised now (#214).
    practised = backfill_practised(session)
    session.commit()
segments = sum(len(m.segments) for m in content.modules)
print(
    f"seed: {len(content.objectives)} objectives, {len(content.modules)} modules, "
    f"{segments} segments, {len(content.review_paths)} review paths, "
    f"{len(content.activities)} activities, {len(content.graphs)} graphs"
)
if kept:
    print(f"seed: left as staff edited them in the portal: {', '.join(kept)}")
if caught_up:
    print(
        "seed: the repository now matches these portal edits, so it decides again: "
        f"{', '.join(caught_up)}"
    )
for problem in problems:
    print(
        "seed: WARNING the repository's content and the portal's edits don't fit together, so the "
        f"content editor will refuse every save until it is fixed in the portal: {problem}"
    )
if demo_problem:
    print(f"seed: demo accounts NOT rebuilt, the previous ones are kept: {demo_problem}")
elif demo:
    print(f"seed: demo accounts {', '.join(a.email for a in demo)}")
    for note in notes:
        print(f"seed: demo progress {note}")
else:
    print("seed: no demo accounts (DEMO_PASSWORD is not set)")
if backfilled:
    print(f"seed: {backfilled} complete modules gained their points (completed before #166)")
if practised:
    print(f"seed: {practised} Practised badges for objectives already secure in practice (#214)")
