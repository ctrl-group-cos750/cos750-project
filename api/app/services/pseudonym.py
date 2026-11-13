"""A student's name in the pilot's CSV files (FR-10.3): not their account id, which is in the staff
portal's addresses (/staff/accounts/<id>) and would put a name to every row (13 Nov audit, A13)."""

import hashlib
import hmac

from app.security import SECRET_KEY


def pseudonym(user_id: int) -> str:
    """A keyed hash (HMAC-SHA256 with the server's secret key) of the account id. Stable, so every
    file and every download agree and can be joined, but it can't be turned back into the id
    without the key. Staff see it on one account's page only, to join the pilot survey's
    participant codes to the data."""
    digest = hmac.new(SECRET_KEY.encode(), f"pilot-export:{user_id}".encode(), hashlib.sha256)
    return "s-" + digest.hexdigest()[:12]
