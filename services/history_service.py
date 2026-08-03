"""History service facade preserving the existing SQLite repository."""

from database.database import HistoryRepository, HistorySnapshot

__all__ = ("HistoryRepository", "HistorySnapshot")
