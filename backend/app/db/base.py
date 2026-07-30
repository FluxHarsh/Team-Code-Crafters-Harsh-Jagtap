"""
Declarative base shared by every ORM model. Alembic's env.py imports
`Base.metadata` (via app.models) as the autogenerate target.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
