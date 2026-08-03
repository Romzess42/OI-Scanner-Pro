"""Detailed non-blocking analysis view opened from the scanner table."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QTabWidget, QVBoxLayout, QWidget

from charts.candlestick_chart import CandlestickChart
from charts.chart_widget import HistoryChart
from charts.funding_chart import FundingChart
from charts.liquidation_chart import LiquidationChart
from charts.oi_chart import OIChart
from charts.volume_chart import VolumeChart
from config import DATABASE_NAME
from database.database import HistoryRepository
from scanner.models import ScannerItem


class CandleLoadWorker(QThread):
    """Fetch public candles without blocking the Qt interface thread."""

    loaded = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        fetch_candles: Callable[[str, str], list[dict[str, float]]],
        symbol: str,
        timeframe: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._fetch_candles = fetch_candles
        self._symbol = symbol
        self._timeframe = timeframe

    def run(self) -> None:
        try:
            self.loaded.emit(self._fetch_candles(self._symbol, self._timeframe))
        except RuntimeError as error:
            self.failed.emit(str(error))


class InstrumentAnalysisDialog(QDialog):
    """Show local metrics immediately and load live candles in the background."""

    _detached_workers: set[CandleLoadWorker] = set()

    def __init__(self, item: ScannerItem, parent=None):
        super().__init__(parent)
        self._item = item
        self._candle_worker: CandleLoadWorker | None = None
        self._closing = False

        self.setWindowTitle(f"Instrument Analysis — {item.symbol}")
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{item.symbol} | {item.exchange} | Score: {item.score} | "
                f"Signal: {item.signal.value or 'Neutral'}"
            )
        )

        tabs = QTabWidget()
        layout.addWidget(tabs)
        repository = HistoryRepository(DATABASE_NAME)
        rows = repository.get_series(item.exchange, item.symbol, item.instrument_type)
        liquidation_events = (
            [] if item.instrument_type == "USDT Spot"
            else repository.get_liquidations(item.exchange, item.symbol)
        )

        self._price_chart = CandlestickChart()
        self._candle_status = QLabel("Preparing live candle request...")
        self._candle_timeframe = QComboBox()
        for label, timeframe in (
            ("15m", "15m"),
            ("1h", "1H"),
            ("4h", "4H"),
            ("1d", "1D"),
            ("1w", "1W"),
            ("1m", "1M"),
        ):
            self._candle_timeframe.addItem(label, timeframe)
        self._candle_timeframe.currentIndexChanged.connect(self._load_candles)

        charts = (
            ("Price", self._price_chart, None),
            ("Open Interest", OIChart(), "open_interest"),
            ("Volume", VolumeChart(), "volume_24h"),
            ("Funding", FundingChart(), "funding_rate"),
            ("Score", HistoryChart("Score", "#EF5350"), "score"),
        )
        for name, chart, field in charts:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            if name == "Price":
                page_layout.addWidget(self._candle_timeframe)
            if field is not None:
                chart.set_series(rows, field)
            page_layout.addWidget(chart)
            if name == "Price":
                page_layout.addWidget(self._candle_status)
            tabs.addTab(page, name)

        signals = "\n".join(
            f"{datetime.fromtimestamp(row['timestamp_ms'] / 1_000, timezone.utc).strftime('%Y-%m-%d %H:%M')}  "
            f"{row.get('signal') or 'Neutral'}  Score {row.get('score', 0)}"
            for row in rows
        ) or "Collecting history..."
        liquidation_chart = LiquidationChart()
        liquidation_chart.set_events(liquidation_events)
        liquidation_page = QWidget()
        liquidation_layout = QVBoxLayout(liquidation_page)
        liquidation_layout.addWidget(liquidation_chart)
        if not liquidation_events:
            liquidation_layout.addWidget(QLabel("Collecting public liquidation events..."))
        tabs.addTab(liquidation_page, "Liquidations")

        signal_page = QWidget()
        signal_layout = QVBoxLayout(signal_page)
        signal_layout.addWidget(QLabel(signals))
        tabs.addTab(signal_page, "Signal History")
        self._load_candles()

    def _load_candles(self, _index: int | None = None) -> None:
        """Start a background request for the selected OHLC period."""
        if self._candle_worker is not None:
            return
        try:
            client = self._create_candle_client()
        except KeyError:
            self._candle_status.setText("Live candles are unavailable for this exchange.")
            return

        timeframe = str(self._candle_timeframe.currentData())
        self._candle_timeframe.setEnabled(False)
        self._candle_status.setText(
            f"Loading public {self._candle_timeframe.currentText()} candles..."
        )
        worker = CandleLoadWorker(client.fetch_ohlc, self._item.symbol, timeframe)
        self._candle_worker = worker
        self._detached_workers.add(worker)
        worker.loaded.connect(self._show_candles)
        worker.failed.connect(self._show_candle_error)
        worker.finished.connect(self._finish_candle_load)
        worker.finished.connect(
            lambda worker=worker: self._detached_workers.discard(worker)
        )
        worker.start()

    def _show_candles(self, candles: list[dict[str, float]]) -> None:
        if self._closing:
            return
        self._price_chart.set_candles(candles)
        self._candle_status.setText(
            f"{len(candles)} public {self._candle_timeframe.currentText()} candles loaded"
        )

    def _show_candle_error(self, _message: str) -> None:
        if not self._closing:
            self._candle_status.setText(
                "Live candles are unavailable; local history remains visible in the other tabs."
            )

    def _finish_candle_load(self) -> None:
        if self._closing:
            return
        self._candle_worker = None
        self._candle_timeframe.setEnabled(True)

    def _create_candle_client(self) -> Any:
        client_by_exchange = {
            "Bybit": ("api.bybit", "BybitClient"),
            "Binance": ("api.binance", "BinanceClient"),
            "OKX": ("api.okx", "OKXClient"),
        }
        module_name, client_name = client_by_exchange[self._item.exchange]
        module = __import__(module_name, fromlist=[client_name])
        return getattr(module, client_name)()

    def closeEvent(self, event) -> None:
        self._closing = True
        worker = self._candle_worker
        if worker is not None:
            for signal, slot in (
                (worker.loaded, self._show_candles),
                (worker.failed, self._show_candle_error),
                (worker.finished, self._finish_candle_load),
            ):
                try:
                    signal.disconnect(slot)
                except RuntimeError:
                    pass
            self._candle_worker = None
        super().closeEvent(event)
