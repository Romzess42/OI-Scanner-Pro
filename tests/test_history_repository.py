"""Tests for SQLite-backed scanner history."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest import TestCase

from database.database import HistoryRepository
from scanner.models import LiquidationEvent, ScannerItem


class HistoryRepositoryTests(TestCase):
    def test_returns_the_latest_snapshot_before_the_requested_time(self):
        with TemporaryDirectory() as directory:
            repository = HistoryRepository(f"{directory}/history.db")
            start = datetime(2026, 8, 3, tzinfo=timezone.utc)

            repository.save_snapshots(
                [
                    self._item(start, open_interest=100.0, volume=1_000.0),
                    self._item(
                        start + timedelta(minutes=10),
                        open_interest=110.0,
                        volume=1_100.0,
                    ),
                ]
            )
            self.assertEqual(repository.count_snapshots(), 2)

            baselines = repository.get_baselines(
                "Bybit",
                ["BTCUSDT", "ETHUSDT"],
                start + timedelta(minutes=5),
            )

            self.assertEqual(set(baselines), {"BTCUSDT"})
            self.assertEqual(baselines["BTCUSDT"].open_interest, 100.0)
            self.assertEqual(baselines["BTCUSDT"].volume_24h, 1_000.0)
            self.assertIsNone(baselines["BTCUSDT"].funding_rate)
            series = repository.get_series("Bybit", "BTCUSDT")
            self.assertEqual(len(series), 2)
            self.assertEqual(series[0]["open_interest"], 100.0)

    def test_upgrades_an_existing_history_database_with_funding_rate(self):
        with TemporaryDirectory() as directory:
            database_path = f"{directory}/history.db"
            with closing(sqlite3.connect(database_path)) as connection, connection:
                connection.execute(
                    """
                    CREATE TABLE history (
                        id INTEGER PRIMARY KEY,
                        exchange TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timestamp_ms INTEGER NOT NULL,
                        open_interest REAL,
                        volume_24h REAL,
                        price REAL
                    )
                    """
                )

            HistoryRepository(database_path)

            with closing(sqlite3.connect(database_path)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(history)")
                }

            self.assertIn("funding_rate", columns)
            self.assertIn("instrument_type", columns)

    def test_persists_alert_journal_entries(self):
        with TemporaryDirectory() as directory:
            database_path = f"{directory}/history.db"
            repository = HistoryRepository(database_path)
            now = datetime(2026, 8, 3, tzinfo=timezone.utc)

            repository.save_alert("Bybit", "BTCUSDT", "Long Buildup", now)

            persisted = HistoryRepository(database_path).get_alerts()
            self.assertEqual(persisted[0]["exchange"], "Bybit")
            self.assertEqual(persisted[0]["symbol"], "BTCUSDT")
            self.assertEqual(persisted[0]["message"], "Long Buildup")

    def test_persists_and_deduplicates_liquidations(self):
        with TemporaryDirectory() as directory:
            repository = HistoryRepository(f"{directory}/history.db")
            event = LiquidationEvent(
                exchange="Bybit", symbol="BTCUSDT", timestamp_ms=1_700_000_000_000,
                side="Buy", quantity=2.0, price=100_000.0,
            )

            repository.save_liquidations([event, event])

            events = repository.get_liquidations("Bybit", "BTCUSDT")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["side"], "Buy")
            self.assertEqual(events[0]["quantity"], 2.0)

    def test_keeps_spot_and_perpetual_history_separate(self):
        with TemporaryDirectory() as directory:
            repository = HistoryRepository(f"{directory}/history.db")
            now = datetime(2026, 8, 3, tzinfo=timezone.utc)
            perpetual = self._item(now, open_interest=100.0, volume=1_000.0)
            spot = replace(perpetual, instrument_type="USDT Spot", open_interest=None)

            repository.save_snapshots([perpetual, spot])

            self.assertEqual(len(repository.get_series("Bybit", "BTCUSDT", "USDT Perpetual")), 1)
            self.assertEqual(len(repository.get_series("Bybit", "BTCUSDT", "USDT Spot")), 1)

    @staticmethod
    def _item(
        updated_at: datetime,
        open_interest: float,
        volume: float,
    ) -> ScannerItem:
        return ScannerItem(
            symbol="BTCUSDT",
            exchange="Bybit",
            instrument_type="USDT Perpetual",
            price=100000.0,
            volume_24h=volume,
            open_interest=open_interest,
            oi_change_pct=None,
            volume_change_pct=None,
            price_change_pct_24h=None,
            price_change_pct=None,
            funding_rate=None,
            updated_at=updated_at,
        )
