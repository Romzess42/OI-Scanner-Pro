"""Tests for the non-blocking candle loader."""

from __future__ import annotations

from unittest import TestCase

from ui.instrument_analysis import CandleLoadWorker


class CandleLoadWorkerTests(TestCase):
    def test_emits_fetched_candles(self):
        received: list[list[dict[str, float]]] = []
        worker = CandleLoadWorker(
            lambda symbol, timeframe: [
                {"timestamp_ms": 1.0, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5}
            ],
            "BTCUSDT",
            "15m",
        )
        worker.loaded.connect(received.append)

        worker.run()

        self.assertEqual(received[0][0]["close"], 1.5)
