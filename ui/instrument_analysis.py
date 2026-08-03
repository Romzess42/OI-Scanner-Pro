"""Detailed local-history view opened from the scanner table."""
from __future__ import annotations
from PySide6.QtWidgets import QDialog, QLabel, QTabWidget, QVBoxLayout, QWidget
from datetime import datetime, timezone
from charts.chart_widget import HistoryChart
from charts.funding_chart import FundingChart
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
        rows = HistoryRepository(DATABASE_NAME).get_series(item.exchange, item.symbol)
        charts = (("Price", HistoryChart("Price", "#FFD54F"), "price"), ("Open Interest", OIChart(), "open_interest"), ("Volume", VolumeChart(), "volume_24h"), ("Funding", FundingChart(), "funding_rate"), ("Score", HistoryChart("Score", "#EF5350"), "score"))
        for name, chart, field in charts:
            page = QWidget(); page_layout = QVBoxLayout(page); chart.set_series(rows, field); page_layout.addWidget(chart); tabs.addTab(page, name)
        signals = "\n".join(f"{datetime.fromtimestamp(row['timestamp_ms'] / 1_000, timezone.utc).strftime('%Y-%m-%d %H:%M')}  {row.get('signal') or 'Neutral'}  Score {row.get('score', 0)}" for row in rows) or "Collecting history..."
        for name, value in (("Liquidations", "No public liquidation history loaded for this market."), ("Signal History", signals)):
            page = QWidget(); page_layout = QVBoxLayout(page); page_layout.addWidget(QLabel(value)); tabs.addTab(page, name)
