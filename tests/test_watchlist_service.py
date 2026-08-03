from tempfile import TemporaryDirectory
from unittest import TestCase
from services.watchlist_service import WatchlistService

class WatchlistServiceTests(TestCase):
    def test_persists_add_and_remove(self):
        with TemporaryDirectory() as directory:
            service=WatchlistService(f"{directory}/watchlist.db")
            service.add("Bybit","BTCUSDT")
            self.assertTrue(service.contains("Bybit","BTCUSDT"))
            service.remove("Bybit","BTCUSDT")
            self.assertFalse(service.contains("Bybit","BTCUSDT"))
