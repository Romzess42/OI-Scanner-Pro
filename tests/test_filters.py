"""Tests for signal detection, scoring and scanner filters."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase

from scanner.filters import (
    ScannerFilters,
    SignalThresholds,
    apply_filters,
    calculate_score,
    determine_signal,
)
from scanner.models import InstrumentType, ScannerItem, SignalType


class ScannerFilterTests(TestCase):
    def test_detects_long_and_short_buildup(self):
        long_item = self._item(oi=0.30, volume=0.40, price=0.02)
        short_item = self._item(oi=0.30, volume=0.40, price=-0.02)

        self.assertEqual(determine_signal(long_item), SignalType.LONG_BUILDUP)
        self.assertEqual(determine_signal(short_item), SignalType.SHORT_BUILDUP)

    def test_detects_exit_signals(self):
        long_exit = self._item(oi=-0.25, volume=None, price=-0.01)
        short_exit = self._item(oi=-0.25, volume=None, price=0.01)

        self.assertEqual(determine_signal(long_exit), SignalType.LONG_EXIT)
        self.assertEqual(determine_signal(short_exit), SignalType.SHORT_EXIT)

    def test_applies_oi_volume_and_signal_filters(self):
        qualifying = replace(
            self._item(oi=0.35, volume=0.45, price=0.02),
            signal=SignalType.LONG_BUILDUP,
        )
        weak = replace(
            self._item(oi=0.10, volume=0.50, price=0.02),
            signal=SignalType.LONG_BUILDUP,
        )
        filters = ScannerFilters(
            min_oi_change=0.20,
            min_volume_change=0.30,
            signal=SignalType.LONG_BUILDUP,
        )

        self.assertEqual(apply_filters([qualifying, weak], filters), [qualifying])

    def test_filters_symbols_case_insensitively_and_combines_with_thresholds(self):
        bitcoin = self._item(oi=0.35, volume=0.45, price=0.02)
        ethereum = replace(bitcoin, symbol="ETHUSDT", oi_change_pct=0.10)
        filters = ScannerFilters(symbol_query="btc", min_oi_change=0.20)

        self.assertEqual(apply_filters([bitcoin, ethereum], filters), [bitcoin])

    def test_score_rewards_large_changes_and_flat_price_accumulation(self):
        item = self._item(oi=0.30, volume=0.50, price=0.005)
        self.assertEqual(calculate_score(item, SignalThresholds()), 10)

    def test_filters_multiple_exchanges_and_market_types(self):
        perpetual = self._item(oi=0.3, volume=0.4, price=0.02)
        spot = replace(perpetual, exchange="Binance", instrument_type="USDT Spot")
        futures = replace(perpetual, exchange="OKX", instrument_type="USDT Futures")
        filters = ScannerFilters(
            exchanges=frozenset(("Binance", "OKX")),
            instrument_types=frozenset((InstrumentType.SPOT, InstrumentType.FUTURES)),
        )

        self.assertEqual(apply_filters([perpetual, spot, futures], filters), [spot, futures])

    @staticmethod
    def _item(
        oi: float | None,
        volume: float | None,
        price: float | None,
    ) -> ScannerItem:
        return ScannerItem(
            symbol="BTCUSDT",
            exchange="Bybit",
            instrument_type="USDT Perpetual",
            price=100000.0,
            volume_24h=50000000.0,
            open_interest=10000000.0,
            oi_change_pct=oi,
            volume_change_pct=volume,
            price_change_pct_24h=None,
            price_change_pct=price,
            funding_rate=0.0,
            updated_at=datetime.now(timezone.utc),
        )
