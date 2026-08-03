"""SQLite-backed instrument watchlist."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from pathlib import Path
class WatchlistService:
    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con, con: con.execute("CREATE TABLE IF NOT EXISTS watchlist (exchange TEXT NOT NULL, symbol TEXT NOT NULL, PRIMARY KEY(exchange, symbol))")
    def add(self, exchange: str, symbol: str) -> None:
        with closing(sqlite3.connect(self.path)) as con, con: con.execute("INSERT OR IGNORE INTO watchlist VALUES (?, ?)",(exchange,symbol))
    def remove(self, exchange: str, symbol: str) -> None:
        with closing(sqlite3.connect(self.path)) as con, con: con.execute("DELETE FROM watchlist WHERE exchange=? AND symbol=?",(exchange,symbol))
    def all(self) -> set[tuple[str,str]]:
        with closing(sqlite3.connect(self.path)) as con: return set(con.execute("SELECT exchange,symbol FROM watchlist"))
    def contains(self, exchange: str, symbol: str) -> bool:
        return (exchange, symbol) in self.all()
