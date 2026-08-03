"""Tests for supported-exchange selection."""

from unittest import TestCase

from api.exchange_manager import ExchangeManager


class FakeClient:
    def __init__(self, exchange_name):
        self.exchange_name = exchange_name

    def fetch_usdt_perpetual_tickers(self):
        return []

    def fetch_previous_close_prices(self, symbols, timeframe):
        return {}


class ExchangeManagerTests(TestCase):
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
