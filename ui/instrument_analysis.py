"""Detailed local-history view opened from the scanner table."""
from __future__ import annotations
from PySide6.QtWidgets import QComboBox, QDialog, QLabel, QTabWidget, QVBoxLayout, QWidget
from datetime import datetime, timezone
from charts.chart_widget import HistoryChart
from charts.candlestick_chart import CandlestickChart
from charts.funding_chart import FundingChart
from charts.liquidation_chart import LiquidationChart
from charts.oi_chart import OIChart
from charts.volume_chart import VolumeChart
from config import DATABASE_NAME
from database.database import HistoryRepository
from scanner.models import ScannerItem

class InstrumentAnalysisDialog(QDialog):
    def __init__(self, item: ScannerItem, parent=None):
        super().__init__(parent); self.setWindowTitle(f"Instrument Analysis — {item.symbol}"); self.resize(900,600)
        layout=QVBoxLayout(self); layout.addWidget(QLabel(f"{item.symbol} | {item.exchange} | Score: {item.score} | Signal: {item.signal.value or 'Neutral'}"))
        tabs=QTabWidget(); layout.addWidget(tabs)
        repository = HistoryRepository(DATABASE_NAME)
        rows = repository.get_series(item.exchange, item.symbol)
        liquidation_events = repository.get_liquidations(item.exchange, item.symbol)
        self._item = item
        self._price_chart = CandlestickChart()
        self._candle_status = QLabel()
        self._candle_timeframe = QComboBox()
        for label, timeframe in (
            ("15m", "15m"), ("1h", "1H"), ("4h", "4H"),
            ("1d", "1D"), ("1w", "1W"), ("1m", "1M"),
        ):
            self._candle_timeframe.addItem(label, timeframe)
        self._candle_timeframe.currentIndexChanged.connect(self._load_candles)

        charts = (("Price", self._price_chart, None), ("Open Interest", OIChart(), "open_interest"), ("Volume", VolumeChart(), "volume_24h"), ("Funding", FundingChart(), "funding_rate"), ("Score", HistoryChart("Score", "#EF5350"), "score"))
        for name, chart, field in charts:
            page = QWidget(); page_layout = QVBoxLayout(page)
            if name == "Price":
                page_layout.addWidget(self._candle_timeframe)
            if field is not None:
                chart.set_series(rows, field)
            page_layout.addWidget(chart)
            if name == "Price":
                page_layout.addWidget(self._candle_status)
            tabs.addTab(page, name)
        signals = "\n".join(f"{datetime.fromtimestamp(row['timestamp_ms'] / 1_000, timezone.utc).strftime('%Y-%m-%d %H:%M')}  {row.get('signal') or 'Neutral'}  Score {row.get('score', 0)}" for row in rows) or "Collecting history..."
        liquidation_chart = LiquidationChart()
        liquidation_chart.set_events(liquidation_events)
        liquidation_page = QWidget(); liquidation_layout = QVBoxLayout(liquidation_page)
        liquidation_layout.addWidget(liquidation_chart)
        if not liquidation_events:
            liquidation_layout.addWidget(QLabel("Collecting public liquidation events..."))
        tabs.addTab(liquidation_page, "Liquidations")
        for name, value in (("Signal History", signals),):
            page = QWidget(); page_layout = QVBoxLayout(page); page_layout.addWidget(QLabel(value)); tabs.addTab(page, name)
        self._load_candles()

    def _load_candles(self) -> None:
        """Load the selected exchange's public OHLC data for the visible chart."""
        client_by_exchange = {
            "Bybit": ("api.bybit", "BybitClient"),
            "Binance": ("api.binance", "BinanceClient"),
            "OKX": ("api.okx", "OKXClient"),
        }
        try:
            module_name, client_name = client_by_exchange[self._item.exchange]
            module = __import__(module_name, fromlist=[client_name])
            timeframe = str(self._candle_timeframe.currentData())
            candles = getattr(module, client_name)().fetch_ohlc(self._item.symbol, timeframe)
        except (KeyError, RuntimeError):
            self._candle_status.setText("Live candles are unavailable; local history remains visible in the other tabs.")
            return
        self._price_chart.set_candles(candles)
        self._candle_status.setText(
            f"{len(candles)} public {self._candle_timeframe.currentText()} candles loaded"
        )
