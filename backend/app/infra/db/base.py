"""Database metadata root; Phase 0 has no application tables."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
