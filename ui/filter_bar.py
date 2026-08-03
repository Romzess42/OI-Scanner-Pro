from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
    QCheckBox,
)

from scanner.filters import ScannerFilters
from scanner.models import SignalType


class FilterBar(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()

        layout.addWidget(QLabel("Exchange"))

        self.exchange = QComboBox()
        self.exchange.addItem("All", None)
        self.exchange.addItem("Bybit", "Bybit")
        self.exchange.addItem("Binance", "Binance")
        self.exchange.addItem("OKX", "OKX")
        layout.addWidget(self.exchange)

        layout.addWidget(QLabel("Type"))

        self.instrument = QComboBox()
        self.instrument.addItems(
            [
                "Perpetual",
                "Futures",
                "Spot",
            ]
        )
        layout.addWidget(self.instrument)

        layout.addWidget(QLabel("Timeframe"))

        self.timeframe = QComboBox()
        self.timeframe.addItems(
            [
                "15m",
                "1H",
                "4H",
                "1D",
                "1W",
                "1M",
            ]
        )
        layout.addWidget(self.timeframe)

        layout.addWidget(QLabel("OI"))

        self.oi_change = QComboBox()
        self.oi_change.addItem("All", None)
        for threshold in (20, 30, 50, 100):
            self.oi_change.addItem(
                f"> {threshold}%",
                ("min", threshold / 100),
            )
        for threshold in (20, 30, 50):
            self.oi_change.addItem(
                f"< -{threshold}%",
                ("max", -threshold / 100),
            )
        layout.addWidget(self.oi_change)

        layout.addWidget(QLabel("Volume"))

        self.volume_change = QComboBox()
        self.volume_change.addItem("All", None)
        for threshold in (20, 30, 50, 100):
            self.volume_change.addItem(f"> {threshold}%", threshold / 100)
        layout.addWidget(self.volume_change)

        layout.addWidget(QLabel("Signal"))

        self.signal = QComboBox()
        self.signal.addItem("All", None)
        for signal in (
            SignalType.LONG_BUILDUP,
            SignalType.SHORT_BUILDUP,
            SignalType.LONG_UNWINDING,
            SignalType.SHORT_COVERING,
        ):
            self.signal.addItem(signal.value, signal)
        layout.addWidget(self.signal)

        layout.addWidget(QLabel("Search"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search symbol: BTC, BT...")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.watchlist_only = QCheckBox("Watchlist")
        layout.addWidget(self.watchlist_only)

        self.refresh = QPushButton("Refresh")

        layout.addWidget(self.refresh)

        layout.addStretch()

        self.setLayout(layout)

    def current_filters(self) -> ScannerFilters:
        """Return the selected domain filters without coupling UI to the service."""
        oi_filter = self.oi_change.currentData()
        min_oi_change = None
        max_oi_change = None
        if oi_filter:
            direction, threshold = oi_filter
            if direction == "min":
                min_oi_change = threshold
            else:
                max_oi_change = threshold

        return ScannerFilters(
            symbol_query=self.search.text().strip(),
            exchange=self.exchange.currentData(),
            min_oi_change=min_oi_change,
            max_oi_change=max_oi_change,
            min_volume_change=self.volume_change.currentData(),
            signal=self.signal.currentData(),
        )
