"""Every order of a Parsons problem's lines that Python can run, for the tests that check the
accepted orders against what really works (FR-5.4, issue #145).

Not a test module (no `test_` prefix): test_module_4.py and test_module_6.py import it.
"""

from collections.abc import Iterator


def _indent(text: str) -> int:
    return len(text) - len(text.lstrip())


def runnable_orders(lines: dict[int, str]) -> Iterator[list[int]]:
    """Each order of all of `lines` (id → text, indentation included) that Python would compile:
    a line ending in `:` is followed by one indented four spaces more, any other line by one at
    its own indentation or at an enclosing one, and the last line opens no block. Pruning on
    that keeps the search small (2,880 orders of the 13 BFS lines, against 13! ≈ 6.2 billion),
    and it misses no order Python could run, because the indentation is part of each line's
    text, so a student can't change it."""

    def extend(order: list[int], left: set[int], open_at: list[int]) -> Iterator[list[int]]:
        if not left:
            if not lines[order[-1]].rstrip().endswith(":"):
                yield list(order)
            return
        last = lines[order[-1]] if order else None
        for line in sorted(left):
            depth = _indent(lines[line])
            if last is None:
                fits, levels = depth == 0, [0]
            elif last.rstrip().endswith(":"):
                fits, levels = depth == _indent(last) + 4, [*open_at, depth]
            else:
                fits = depth in open_at
                levels = open_at[: open_at.index(depth) + 1] if fits else open_at
            if fits:
                order.append(line)
                left.remove(line)
                yield from extend(order, left, levels)
                order.pop()
                left.add(line)

    yield from extend([], set(lines), [0])
