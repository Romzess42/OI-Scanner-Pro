"""Lightweight OHLC candlestick chart for Instrument Analysis."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPicture


class CandlestickItem(pg.GraphicsObject):
    def __init__(self, candles: list[dict[str, float]]):
        super().__init__()
        self._picture = QPicture()
        painter = QPainter(self._picture)
        for candle in candles:
            x = candle["timestamp_ms"] / 1_000
            opening, high, low, close = (candle[key] for key in ("open", "high", "low", "close"))
            color = QColor("#26A69A" if close >= opening else "#EF5350")
            painter.setPen(QPen(color))
            painter.drawLine(x, low, x, high)
            painter.fillRect(QRectF(x - 20, min(opening, close), 40, max(abs(close - opening), 0.000001)), color)
        painter.end()

    def paint(self, painter, *args):
        painter.drawPicture(0, 0, self._picture)

    def boundingRect(self):
        return QRectF(self._picture.boundingRect())


class CandlestickChart(pg.PlotWidget):
    def __init__(self):
        super().__init__(title="Price", axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
        self.showGrid(x=True, y=True, alpha=0.2)

    def set_candles(self, candles: list[dict[str, float]]) -> None:
        self.clear()
        if candles:
            self.addItem(CandlestickItem(candles))
