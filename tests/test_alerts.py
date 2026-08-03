"""Tests for local alert cooldown and thresholds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from scanner.filters import SignalThresholds
from scanner.models import ScannerItem, SignalType
from utils.alerts import LocalAlertManager


class LocalAlertManagerTests(TestCase):
    def test_emits_once_until_the_cooldown_expires(self):
        manager = LocalAlertManager(cooldown_seconds=60)
        item = self._item()
        thresholds = SignalThresholds()
        now = datetime(2026, 8, 3, tzinfo=timezone.utc)

        self.assertEqual(len(manager.collect([item], thresholds, now)), 1)
        self.assertEqual(
            manager.collect([item], thresholds, now + timedelta(seconds=30)),
            [],
        )
        self.assertEqual(
            len(manager.collect([item], thresholds, now + timedelta(seconds=60))),
            1,
        )

    def test_does_not_emit_when_score_is_below_the_configured_threshold(self):
        item = self._item()
        thresholds = SignalThresholds(alert_score=item.score + 1)

        self.assertEqual(LocalAlertManager().collect([item], thresholds), [])

    @staticmethod
    def _item() -> ScannerItem:
        return ScannerItem(
            symbol="BTCUSDT",
            exchange="Bybit",
            instrument_type="USDT Perpetual",
            price=100000.0,
            volume_24h=50000000.0,
            open_interest=10000000.0,
            oi_change_pct=0.35,
            volume_change_pct=0.42,
            price_change_pct_24h=None,
            price_change_pct=0.02,
            funding_rate=0.0002,
            updated_at=datetime.now(timezone.utc),
            signal=SignalType.LONG_BUILDUP,
            score=6,
        )
