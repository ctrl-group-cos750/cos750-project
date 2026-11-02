"""Free text from students: names now, answers later. Add NoHiddenCharacters to every such field."""

import unicodedata

from pydantic import AfterValidator

# Cc: control characters (NUL, newline, bell). Postgres refuses NUL in text and jsonb, so one
# in a request used to crash the API with 500. Cf: invisible formatting (zero-width space,
# right-to-left override), which can make one name look like another.
_REFUSED = {"Cc", "Cf", "Cs", "Co", "Cn"}


def _no_hidden_characters(value: str) -> str:
    if any(unicodedata.category(c) in _REFUSED for c in value):
        raise ValueError("Use letters, numbers, spaces and punctuation only.")
    return unicodedata.normalize("NFC", value)


NoHiddenCharacters = AfterValidator(_no_hidden_characters)
