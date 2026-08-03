"""Persistent local notification journal."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from config import DATABASE_NAME
from database.database import HistoryRepository
@dataclass(frozen=True, slots=True)
class AlertJournalEntry: symbol: str; exchange: str; message: str; created_at: datetime
class AlertService:
    def __init__(self, repository=None): self._entries=[]; self._repository=repository or HistoryRepository(DATABASE_NAME)
    def record(self,symbol,exchange,message):
        entry=AlertJournalEntry(symbol,exchange,message,datetime.now(timezone.utc)); self._entries.append(entry); self._repository.save_alert(exchange,symbol,message,entry.created_at); return entry
    def entries(self): return list(reversed(self._entries))
