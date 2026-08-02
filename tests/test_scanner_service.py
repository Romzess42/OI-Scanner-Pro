"""Unit tests for Bybit data normalization."""

from __future__ import annotations

from unittest import TestCase

from api.bybit import BybitClient
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


class ScannerServiceTests(TestCase):
    def test_refresh_normalizes_and_sorts_tickers_by_volume(self):
        client = FakeBybitClient()
        items = ScannerService(client).refresh("1H")

        self.assertEqual([item.symbol for item in items], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(items[0].exchange, "Bybit")
        self.assertEqual(items[0].instrument_type, "USDT Perpetual")
        self.assertEqual(items[0].price, 100000.0)
        self.assertEqual(items[1].price_change_pct_24h, -0.0125)
        self.assertIsNone(items[0].funding_rate)
        self.assertAlmostEqual(items[0].price_change_pct, 0.020408, places=6)
        self.assertEqual(client.timeframe, "1H")
        self.assertEqual(client.symbols, ["BTCUSDT", "ETHUSDT"])

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
        items = ScannerService(client).refresh("15m")

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
