"""The authoring templates (app/seed/templates, issue #64) and `python -m app.seed --check`. A
template that no longer fits the schema fails here, so the guide's examples can't rot."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

from app.schemas.activities import ActivityKind
from app.seed import TEMPLATES, read_fixtures, read_templates

API_DIR = Path(__file__).resolve().parent.parent


def test_every_activity_kind_has_a_template_that_validates() -> None:
    templates = read_templates()  # raises, naming the file, if a template is invalid
    assert set(templates) == set(get_args(ActivityKind))


@pytest.mark.parametrize("kind", get_args(ActivityKind))
def test_each_template_shows_what_the_guide_asks_for(kind: str) -> None:
    activity = read_templates()[kind]
    # The four-level hint ladder (ID document §7.5).
    assert sorted(h.level for h in activity.hints) == [1, 2, 3, 4]
    # Tagged with its objective (a template is never diagnostic, which has none) and a purpose.
    assert activity.objective_id is not None
    # Feedback on a right answer, and a reason for wrong ones where the kind takes them
    # (Parsons and trace tables are explained line by line and row by row by the checker).
    assert activity.solution.get("explanation")
    if kind not in ("trace", "parsons"):
        assert activity.solution.get("feedback")


def test_templates_are_not_loaded_as_content() -> None:
    template_ids = {a.id for a in read_templates().values()}
    assert not template_ids & {a.id for a in read_fixtures().activities}


def test_a_broken_template_is_refused(tmp_path: Path) -> None:
    broken = json.loads((TEMPLATES / "multiple_choice.json").read_text(encoding="utf-8"))
    broken["solution"]["correct"] = "z"
    (tmp_path / "multiple_choice.json").write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(ValueError, match=r"templates/multiple_choice\.json"):
        read_templates(tmp_path)


def test_a_template_under_the_wrong_kind_name_is_refused(tmp_path: Path) -> None:
    text = (TEMPLATES / "multiple_choice.json").read_text(encoding="utf-8")
    (tmp_path / "matching.json").write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="holds a multiple_choice activity"):
        read_templates(tmp_path)


def test_the_check_command_passes_on_the_committed_content() -> None:
    run = subprocess.run(
        [sys.executable, "-m", "app.seed", "--check"],
        cwd=API_DIR,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert "fixtures valid" in run.stdout
    assert "templates valid" in run.stdout
