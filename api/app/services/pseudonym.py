"""A student's name in the pilot's CSV files (FR-10.3): not their account id, which is in the staff
portal's addresses (/staff/accounts/<id>) and would put a name to every row (13 Nov audit, A13).

Keyed on `PILOT_PSEUDONYM_KEY`, a key of its own, so changing `SECRET_KEY` (which logs everyone
out) never renames every student between two downloads. Unset, it falls back to `SECRET_KEY`
with a warning: fine for local runs and tests, but set it wherever the pilot runs.

The staff portal doesn't show it (#215 review): a page with a student's name and pseudonym side by
side would link every CSV row back to that student. The one member who joins the survey's
participant codes to the data runs `python -m app.pilot_name <email>` on the server instead
(docs/pilot/README.md).
"""

import hashlib
import hmac
import logging
import os

from app.security import SECRET_KEY

logger = logging.getLogger(__name__)


def _key() -> str:
    key = os.environ.get("PILOT_PSEUDONYM_KEY")
    if key:
        return key
    logger.warning(
        "PILOT_PSEUDONYM_KEY is not set: pilot pseudonyms use SECRET_KEY, and change with it"
    )
    return SECRET_KEY


PSEUDONYM_KEY = _key()


def pseudonym(user_id: int) -> str:
    """A keyed hash (HMAC-SHA256 with `PSEUDONYM_KEY`) of the account id. Stable, so every file and
    every download agree and can be joined, but it can't be turned back into the id without the
    key."""
    digest = hmac.new(PSEUDONYM_KEY.encode(), f"pilot-export:{user_id}".encode(), hashlib.sha256)
    return "s-" + digest.hexdigest()[:12]
