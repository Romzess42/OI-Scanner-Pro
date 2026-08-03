"""Unit tests for Bybit data normalization."""

from __future__ import annotations

from unittest import TestCase

from api.bybit import BybitClient
from database.database import HistorySnapshot
from scanner.models import SignalType
from scanner.scanner import ScannerService


class FakeBybitClient:
    def fetch_usdt_perpetual_tickers(self):
        return [
            {
                "symbol": "ETHUSDT",
                "lastPrice": "3500.25",
                "turnover24h": "25000000",
                "openInterest": "9900000",
                "price24hPcnt": "-0.0125",
                "fundingRate": "0.0001",
            },
            {
                "symbol": "BTCUSDT",
                "lastPrice": "100000",
                "turnover24h": "50000000",
                "openInterest": "12000000",
                "price24hPcnt": "0.025",
                "fundingRate": "",
            },
        ]

    def fetch_previous_close_prices(self, symbols, timeframe):
        self.symbols = symbols
        self.timeframe = timeframe
        return {
            "BTCUSDT": 98000.0,
            "ETHUSDT": 3550.0,
        }


class FakeHistoryRepository:
    def __init__(self, baselines=None):
        self.baselines = baselines or {}
        self.saved_items = []
        self.requested_exchange = None
        self.requested_symbols = []
        self.requested_before = None

    def get_baselines(self, exchange, symbols, before):
        self.requested_exchange = exchange
        self.requested_symbols = symbols
        self.requested_before = before
        return self.baselines

    def save_snapshots(self, items):
        self.saved_items = items

    def count_snapshots(self):
        return len(self.saved_items)


class ScannerServiceTests(TestCase):
    def test_refresh_normalizes_and_sorts_tickers_by_volume(self):
        client = FakeBybitClient()
        history = FakeHistoryRepository()
        service = ScannerService(client, history)
        items = service.refresh("1H")

        self.assertEqual([item.symbol for item in items], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(items[0].exchange, "Bybit")
        self.assertEqual(items[0].instrument_type, "USDT Perpetual")
        self.assertEqual(items[0].price, 100000.0)
        self.assertEqual(items[1].price_change_pct_24h, -0.0125)
        self.assertIsNone(items[0].funding_rate)
        self.assertAlmostEqual(items[0].price_change_pct, 0.020408, places=6)
        self.assertEqual(client.timeframe, "1H")
        self.assertEqual(client.symbols, ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(history.requested_exchange, "Bybit")
        self.assertEqual(history.saved_items, items)
        self.assertEqual(
            service.last_history_status.message,
            "History: 1H collecting | Saved: 2 | Total: 2",
        )

    def test_refresh_calculates_oi_and_volume_changes_from_history(self):
        history = FakeHistoryRepository(
            {
                "BTCUSDT": HistorySnapshot(
                    symbol="BTCUSDT",
                    open_interest=10000000.0,
                    volume_24h=40000000.0,
                    price=98000.0,
                    funding_rate=0.00005,
                )
            }
        )
        service = ScannerService(FakeBybitClient(), history)
        items = service.refresh("15m")
        btc = next(item for item in items if item.symbol == "BTCUSDT")
        eth = next(item for item in items if item.symbol == "ETHUSDT")

        self.assertAlmostEqual(btc.oi_change_pct, 0.2)
        self.assertAlmostEqual(btc.volume_change_pct, 0.25)
        self.assertEqual(btc.signal, SignalType.LONG_BUILDUP)
        self.assertIsNone(eth.oi_change_pct)
        self.assertIsNone(eth.volume_change_pct)
        self.assertEqual(
            service.last_history_status.message,
            "History: 15m 1/2 ready | Saved: 2 | Total: 2",
        )

    def test_refresh_requests_price_history_for_only_top_100_by_volume(self):
        class ManyTickerClient:
            def __init__(self):
                self.symbols = []

            def fetch_usdt_perpetual_tickers(self):
                return [
                    {
                        "symbol": f"COIN{number}USDT",
                        "lastPrice": "1",
                        "turnover24h": str(number),
                    }
                    for number in range(101)
                ]

            def fetch_previous_close_prices(self, symbols, timeframe):
                self.symbols = symbols
                return {}

        client = ManyTickerClient()
        items = ScannerService(client, FakeHistoryRepository()).refresh("15m")

        self.assertEqual(len(items), 101)
        self.assertEqual(len(client.symbols), 100)
        self.assertEqual(client.symbols[0], "COIN100USDT")
        self.assertNotIn("COIN0USDT", client.symbols)

    def test_usdt_perpetual_filter_accepts_only_trading_linear_usdt_contracts(self):
        self.assertTrue(
            BybitClient.is_usdt_perpetual(
                {
                    "contractType": "LinearPerpetual",
                    "settleCoin": "USDT",
                    "status": "Trading",
                }
            )
        )
        self.assertFalse(
            BybitClient.is_usdt_perpetual(
                {
                    "contractType": "LinearPerpetual",
                    "settleCoin": "USDC",
                    "status": "Trading",
                }
            )
        )
