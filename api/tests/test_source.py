from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCES = [
    p
    for folder in (
        "api/app",
        "api/tests",
        "api/migrations",
        "runner/runner",
        "runner/tests",
        "web/src",
        "scripts",
    )
    for p in (REPO / folder).rglob("*")
    if p.suffix in {".py", ".ts", ".tsx", ".css", ".sh", ".mjs"}
]

# Bidirectional controls and invisible characters. In source code they can make code read
# differently from how it runs ("Trojan Source", CVE-2021-42574). Tests that need them write
# them as escapes, such as "\u202e".
HIDDEN = {
    chr(c) for c in [*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200B, 0x200E, 0x200F, 0xFEFF]
}


def test_the_scan_finds_the_source() -> None:
    assert len(SOURCES) > 20


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(REPO)))
def test_no_hidden_characters_in_source(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    found = sorted({f"U+{ord(c):04X}" for c in text if c in HIDDEN})
    assert not found, f"{path.relative_to(REPO)} contains {', '.join(found)}: write them as escapes"
