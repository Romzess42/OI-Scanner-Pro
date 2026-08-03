"""Reusable pyqtgraph time-series widget for local scanner history."""

from __future__ import annotations

import pyqtgraph as pg


class HistoryChart(pg.PlotWidget):
    def __init__(self, title: str, color: str):
        super().__init__(title=title, axisItems={"bottom": pg.DateAxisItem(orientation="bottom")})
        self.showGrid(x=True, y=True, alpha=0.2)
        self._curve = self.plot(pen=pg.mkPen(color, width=2))

    def set_series(self, rows: list[dict], field: str) -> None:
        points = [(row.get("timestamp_ms", 0) / 1000, row.get(field)) for row in rows if row.get(field) is not None]
        self._curve.setData([point[0] for point in points], [point[1] for point in points])
