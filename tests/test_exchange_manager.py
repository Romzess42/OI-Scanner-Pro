"""Tests for supported-exchange selection."""

from unittest import TestCase

from api.exchange_manager import ExchangeManager
from api.binance import BinanceClient
from api.okx import OKXClient
from charts.liquidation_chart import LiquidationChart


class FakeClient:
    def __init__(self, exchange_name):
        self.exchange_name = exchange_name

    def fetch_usdt_perpetual_tickers(self):
        return []

    def fetch_previous_close_prices(self, symbols, timeframe):
        return {}


class ExchangeManagerTests(TestCase):
    def test_binance_ohlc_is_normalized(self):
        class CandleClient(BinanceClient):
            def _get(self, path, params=None):
                return [["1000", "1", "3", "0.5", "2"], ["2000", "2", "4", "1", "3"]]

        candles = CandleClient().fetch_ohlc("BTCUSDT", "15m", 2)

        self.assertEqual(candles[0]["timestamp_ms"], 1000.0)
        self.assertEqual(candles[-1]["close"], 3.0)

    def test_binance_force_order_is_normalized(self):
        events = BinanceClient.parse_liquidation_message(
            {
                "stream": "btcusdt@forceOrder",
                "data": {
                    "e": "forceOrder", "E": 1_700_000_000_000,
                    "o": {"s": "BTCUSDT", "S": "SELL", "q": "0.25", "p": "100000", "ap": "99900"},
                },
            }
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].exchange, "Binance")
        self.assertEqual(events[0].side, "SELL")
        self.assertEqual(events[0].price, 99900.0)
        self.assertTrue(
            LiquidationChart._is_long_liquidation(
                {"exchange": "Binance", "side": events[0].side}
            )
        )

    def test_binance_book_ticker_is_a_price_fallback(self):
        update = BinanceClient.parse_ticker_message(
            {"stream": "btcusdt@bookTicker", "data": {"s": "BTCUSDT", "b": "99999", "a": "100001"}}
        )

        self.assertEqual(update["symbol"], "BTCUSDT")
        self.assertEqual(update["lastPrice"], "100001")
        self.assertIsNone(update["turnover24h"])

    def test_binance_market_stream_includes_ticker_quote_and_liquidation(self):
        url = BinanceClient.market_stream_url(["BTCUSDT"])

        self.assertIn("btcusdt@ticker", url)
        self.assertIn("btcusdt@bookTicker", url)
        self.assertIn("btcusdt@forceOrder", url)

    def test_okx_ohlc_is_reversed_to_chronological_order(self):
        class CandleClient(OKXClient):
            def _get(self, path, params):
                return [["2000", "2", "4", "1", "3"], ["1000", "1", "3", "0.5", "2"]]

        candles = CandleClient().fetch_ohlc("BTC-USDT-SWAP", "15m", 2)

        self.assertEqual(candles[0]["timestamp_ms"], 1000.0)
        self.assertEqual(candles[-1]["close"], 3.0)

    def test_selects_all_or_one_registered_exchange(self):
        manager = ExchangeManager(
            [FakeClient("Bybit"), FakeClient("Binance"), FakeClient("OKX")]
        )

        self.assertEqual(manager.exchanges, ("Bybit", "Binance", "OKX"))
        self.assertEqual(
            [client.exchange_name for client in manager.get_clients()],
            ["Bybit", "Binance", "OKX"],
        )
        self.assertEqual(
            [client.exchange_name for client in manager.get_clients("OKX")],
            ["OKX"],
        )
