import pytest
from sqlalchemy.orm import Session

from app.db import get_session


def test_get_session_yields_one_session_per_request() -> None:
    gen = get_session()
    assert isinstance(next(gen), Session)
    with pytest.raises(StopIteration):
        next(gen)
