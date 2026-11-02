"""The rules for a new password. The register page shows the same rules as a checklist
(web/src/auth/passwordRules.ts); change both together.

Only for new passwords: existing accounts can still log in with the password they have.
"""

from collections.abc import Callable
from dataclasses import dataclass

MIN_LENGTH = 8


@dataclass(frozen=True)
class Rule:
    key: str
    message: str
    passes: Callable[[str, str, str], bool]  # (password, email, display name)


def _not_personal(password: str, email: str, display_name: str) -> bool:
    lowered = password.lower()
    words = [email.split("@")[0].lower(), *display_name.lower().split()]
    return not any(len(word) >= 3 and word in lowered for word in words)


RULES = [
    Rule("length", f"Use at least {MIN_LENGTH} characters.", lambda p, e, n: len(p) >= MIN_LENGTH),
    Rule(
        "lower", "Use at least one lowercase letter.", lambda p, e, n: any(c.islower() for c in p)
    ),
    Rule(
        "upper", "Use at least one uppercase letter.", lambda p, e, n: any(c.isupper() for c in p)
    ),
    Rule("number", "Use at least one number.", lambda p, e, n: any(c.isdigit() for c in p)),
    # Anything that isn't a letter or a number, a space included, so passphrases work.
    Rule(
        "symbol",
        "Use at least one symbol, such as ! # or a space.",
        lambda p, e, n: any(not c.isalnum() for c in p),
    ),
    Rule("personal", "Don't use your name or email in your password.", _not_personal),
]


def password_problem(password: str, email: str = "", display_name: str = "") -> str | None:
    """The first rule the password breaks, in words for the student, or None."""
    for rule in RULES:
        if not rule.passes(password, email, display_name):
            return rule.message
    return None
