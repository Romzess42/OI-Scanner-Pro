"""SQLite storage for historical scanner snapshots."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from scanner.models import LiquidationEvent, ScannerItem


@dataclass(frozen=True, slots=True)
class HistorySnapshot:
    """One historical market snapshot used as a percentage-change baseline."""

    symbol: str
    open_interest: float | None
    volume_24h: float | None
    price: float | None
    funding_rate: float | None


class HistoryRepository:
    """Persist and retrieve scanner snapshots in a local SQLite database."""

    def __init__(self, database_path: str | Path):
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_snapshots(self, items: Iterable[ScannerItem]) -> None:
        """Save all items returned by one scanner refresh."""
        rows = [
            (
                item.exchange,
                item.symbol,
                int(item.updated_at.timestamp() * 1_000),
                item.open_interest,
                item.volume_24h,
                item.price,
                item.funding_rate,
                item.score,
                item.signal.value,
            )
            for item in items
        ]
        if not rows:
            return

        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT INTO history (
                    exchange, symbol, timestamp_ms, open_interest, volume_24h, price,
                    funding_rate, score, signal
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_baselines(
        self,
        exchange: str,
        symbols: Iterable[str],
        before: datetime,
    ) -> dict[str, HistorySnapshot]:
        """Return the latest snapshot at or before *before* for every symbol."""
        unique_symbols = list(dict.fromkeys(symbols))
        if not unique_symbols:
            return {}

        cutoff_ms = int(before.timestamp() * 1_000)
        baselines: dict[str, HistorySnapshot] = {}

        for symbol_group in self._chunked(unique_symbols, 900):
            placeholders = ", ".join("?" for _ in symbol_group)
            query = f"""
                SELECT latest.symbol,
                       latest.open_interest,
                       latest.volume_24h,
                       latest.price,
                       latest.funding_rate
                FROM history AS latest
                INNER JOIN (
                    SELECT symbol, MAX(timestamp_ms) AS timestamp_ms
                    FROM history
                    WHERE exchange = ?
                      AND timestamp_ms <= ?
                      AND symbol IN ({placeholders})
                    GROUP BY symbol
                ) AS selected
                ON latest.symbol = selected.symbol
                   AND latest.timestamp_ms = selected.timestamp_ms
                WHERE latest.exchange = ?
            """
            parameters = [exchange, cutoff_ms, *symbol_group, exchange]

            with closing(self._connect()) as connection:
                rows = connection.execute(query, parameters).fetchall()

            baselines.update(
                {
                    row["symbol"]: HistorySnapshot(
                        symbol=row["symbol"],
                        open_interest=row["open_interest"],
                        volume_24h=row["volume_24h"],
                        price=row["price"],
                        funding_rate=row["funding_rate"],
                    )
                    for row in rows
                }
            )

        return baselines

    def count_snapshots(self) -> int:
        """Return the total number of historical records stored locally."""
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM history").fetchone()
        return int(row["count"])

    def get_series(self, exchange: str, symbol: str, limit: int = 500) -> list[dict[str, object]]:
        """Return chronological local snapshots for Instrument Analysis charts."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT timestamp_ms, price, open_interest, volume_24h, funding_rate,
                       score, signal
                FROM history WHERE exchange = ? AND symbol = ?
                ORDER BY timestamp_ms DESC LIMIT ?
                """,
                (exchange, symbol, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def save_alert(self, exchange: str, symbol: str, message: str, created_at: datetime) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("INSERT INTO alert_journal (timestamp_ms, exchange, symbol, message) VALUES (?, ?, ?, ?)", (int(created_at.timestamp() * 1_000), exchange, symbol, message))

    def get_alerts(self, limit: int = 200) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT timestamp_ms, exchange, symbol, message FROM alert_journal ORDER BY timestamp_ms DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def save_liquidations(self, events: Iterable[LiquidationEvent]) -> None:
        """Persist public liquidation events, ignoring duplicate stream retries."""
        rows = [
            (
                event.exchange,
                event.symbol,
                event.timestamp_ms,
                event.side,
                event.quantity,
                event.price,
            )
            for event in events
        ]
        if not rows:
            return
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO liquidations
                    (exchange, symbol, timestamp_ms, side, quantity, price)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

    def get_liquidations(
        self, exchange: str, symbol: str, limit: int = 500
    ) -> list[dict[str, object]]:
        """Return chronological public liquidation events for one instrument."""
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT timestamp_ms, side, quantity, price
                FROM liquidations
                WHERE exchange = ? AND symbol = ?
                ORDER BY timestamp_ms DESC, id DESC LIMIT ?
                """,
                (exchange, symbol, limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def _initialize(self) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    open_interest REAL,
                    volume_24h REAL,
                    price REAL,
                    funding_rate REAL,
                    score INTEGER NOT NULL DEFAULT 0,
                    signal TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute("CREATE TABLE IF NOT EXISTS alert_journal (id INTEGER PRIMARY KEY, timestamp_ms INTEGER NOT NULL, exchange TEXT NOT NULL, symbol TEXT NOT NULL, message TEXT NOT NULL)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS liquidations (
                    id INTEGER PRIMARY KEY,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    UNIQUE (exchange, symbol, timestamp_ms, side, quantity, price)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_exchange_symbol_time
                ON history (exchange, symbol, timestamp_ms)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_liquidations_exchange_symbol_time
                ON liquidations (exchange, symbol, timestamp_ms)
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(history)").fetchall()
            }
            if "funding_rate" not in columns:
                connection.execute("ALTER TABLE history ADD COLUMN funding_rate REAL")
            if "score" not in columns:
                connection.execute(
                    "ALTER TABLE history ADD COLUMN score INTEGER NOT NULL DEFAULT 0"
                )
            if "signal" not in columns:
                connection.execute(
                    "ALTER TABLE history ADD COLUMN signal TEXT NOT NULL DEFAULT ''"
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _chunked(values: list[str], size: int) -> Iterable[list[str]]:
        for index in range(0, len(values), size):
            yield values[index : index + size]
