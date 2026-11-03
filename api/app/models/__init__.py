# Import every model module here, so Alembic's autogenerate sees all tables.
from app.db import Base
from app.models.activity import Activity, Attempt
from app.models.user import User

__all__ = ["Activity", "Attempt", "Base", "User"]
