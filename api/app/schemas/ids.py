"""Bounds for the integer ids a client sends in a path or a body (#139).

Every id column is a Postgres `integer`, so a value of 2^31 or more can never name a row, and
Postgres refuses to compare it (`NumericValueOutOfRange`), which used to surface as a plain-text
500. Bounding the parameter turns it into a 422 before any query runs. Ids start at 0 (module 0).
"""

from typing import Annotated

from fastapi import Path

DB_INT_MAX = 2**31 - 1  # the largest Postgres `integer`

# A path parameter that names a row: `def get_activity(activity_id: RowId, ...)`.
RowId = Annotated[int, Path(ge=0, le=DB_INT_MAX)]
