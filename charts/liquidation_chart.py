"""Bar chart for real public liquidation events stored locally."""

from __future__ import annotations

import pyqtgraph as pg


class LiquidationChart(pg.PlotWidget):
    """Display long and short liquidations as separate signed notional bars."""

    def __init__(self) -> None:
        super().__init__(
            title="Liquidations (estimated notional)",
            axisItems={"bottom": pg.DateAxisItem(orientation="bottom")},
        )
        self.showGrid(x=True, y=True, alpha=0.2)

    def set_events(self, events: list[dict[str, object]]) -> None:
        self.clear()
        long_x: list[float] = []
        long_y: list[float] = []
        short_x: list[float] = []
        short_y: list[float] = []
        for event in events:
            try:
                timestamp = float(event["timestamp_ms"]) / 1_000
                notional = float(event["quantity"]) * float(event["price"])
            except (KeyError, TypeError, ValueError):
                continue
            # Bybit reports Buy for a liquidated long and Sell for a liquidated short.
            if event.get("side") == "Buy":
                long_x.append(timestamp)
                long_y.append(notional)
            elif event.get("side") == "Sell":
                short_x.append(timestamp)
                short_y.append(-notional)
        width = 30.0
        if long_x:
            self.addItem(pg.BarGraphItem(x=long_x, height=long_y, width=width, brush="#EF5350"))
        if short_x:
            self.addItem(pg.BarGraphItem(x=short_x, height=short_y, width=width, brush="#42A5F5"))
