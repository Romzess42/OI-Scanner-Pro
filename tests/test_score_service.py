"""Tests for ranking scanner items by the existing score rules."""

from datetime import datetime, timezone
from unittest import TestCase

from scanner.filters import SignalThresholds
from scanner.models import ScannerItem
from services.score_service import ScoreService


class ScoreServiceTests(TestCase):
    def test_ranks_highest_score_first(self):
        service = ScoreService()
        low = self._item("LOW", 0.1, 0.1, 0.03)
        high = self._item("HIGH", 0.3, 0.5, 0.005)

        ranked = service.rank([low, high], SignalThresholds())

        self.assertEqual([item.symbol for item in ranked], ["HIGH", "LOW"])
        self.assertEqual(ranked[0].score, 10)
        self.assertEqual(service.top_twenty([low, high], SignalThresholds())[0].symbol, "HIGH")

    @staticmethod
    def _item(symbol, oi, volume, price_change):
        return ScannerItem(
            symbol=symbol,
            exchange="Bybit",
            instrument_type="USDT Perpetual",
            price=1.0,
            volume_24h=1.0,
            open_interest=1.0,
            oi_change_pct=oi,
            volume_change_pct=volume,
            price_change_pct_24h=None,
            price_change_pct=price_change,
            funding_rate=0.0,
            updated_at=datetime.now(timezone.utc),
        )
