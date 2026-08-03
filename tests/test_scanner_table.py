"""Regression tests for visible-row WebSocket updates."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from scanner.models import ScannerItem
from ui.scanner_table import PRICE_COLUMN, ScannerTable


class ScannerTableTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_live_price_update_uses_the_actual_price_column(self):
        table = ScannerTable()
        table.set_items([self._item(100_000.0)])

        table.update_item(self._item(100_001.5))

        self.assertEqual(table.item(0, PRICE_COLUMN).text(), "100,001.5")

    def test_live_update_recreates_a_missing_cell_without_raising(self):
        table = ScannerTable()
        table.set_items([self._item(100_000.0)])
        table.takeItem(0, PRICE_COLUMN)

        table.update_item(self._item(100_001.5))

        self.assertIsNotNone(table.item(0, PRICE_COLUMN))

    @staticmethod
    def _item(price: float) -> ScannerItem:
        return ScannerItem(
            symbol="BTCUSDT", exchange="Bybit", instrument_type="USDT Perpetual",
            price=price, volume_24h=1_000_000.0, open_interest=2_000_000.0,
            oi_change_pct=None, volume_change_pct=None, price_change_pct_24h=None,
            price_change_pct=None, funding_rate=None,
            updated_at=datetime.now(timezone.utc),
        )
