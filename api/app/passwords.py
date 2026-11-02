"""Which new passwords are too easy to guess (NIST SP 800-63B §5.1.1.2).

Argon2 makes each guess slow, but a common password still falls in seconds: in the security
review, "password1" was cracked from a stolen hash in 0.26 s. So a new password is refused when it
is a common one, a common one with digits or symbols added, built from the student's own name or
email, about this site, or the same few characters repeated. Only for new passwords: existing
accounts can still log in.
"""

import re
from functools import cache
from pathlib import Path

_LIST = Path(__file__).parent / "data" / "common-passwords.txt"
_SITE_WORDS = ("ctrlacademy", "ctrlgroup", "controlgroup", "cos212")

TOO_COMMON = "This password is too common. Choose one that's harder to guess."
PERSONAL = "Don't use your name, your email or the site's name in your password."
REPETITIVE = "Use more than three different characters."


@cache
def common_passwords() -> frozenset[str]:
    return frozenset(line.strip() for line in _LIST.read_text(encoding="utf-8").splitlines())


def password_problem(password: str, email: str = "", display_name: str = "") -> str | None:
    """What's wrong with a new password, in words for the student, or None if it's fine."""
    lowered = password.lower()
    common = common_passwords()
    # "password123", "Dragon2024!": a common password with digits and symbols on the end.
    base = re.sub(r"[\d\W_]+$", "", lowered)
    if lowered in common or (len(base) >= 4 and base in common):
        return TOO_COMMON
    squashed = re.sub(r"[\W_]+", "", lowered)
    personal = [email.split("@")[0].lower(), *display_name.lower().split()]
    if any(len(word) >= 4 and word in lowered for word in personal) or any(
        word in squashed for word in _SITE_WORDS
    ):
        return PERSONAL
    if len(set(password)) <= 3:
        return REPETITIVE
    return None
