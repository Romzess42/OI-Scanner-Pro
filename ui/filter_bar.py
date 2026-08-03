"""Scanner filters, multi-select market menus and refresh controls."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from scanner.filters import ScannerFilters
from scanner.models import InstrumentType, SignalType


class MultiSelectMenuButton(QToolButton):
    """A compact menu button whose checkboxes support multiple selections."""

    selection_changed = Signal()

    def __init__(
        self, all_label: str, options: Iterable[tuple[str, object]], selected: Iterable[object]
    ) -> None:
        super().__init__()
        self._all_label = all_label
        self._boxes: dict[object, QCheckBox] = {}
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        self.setMenu(menu)
        selected_values = set(selected)
        for label, value in options:
            box = QCheckBox(label)
            box.setChecked(value in selected_values)
            action = QWidgetAction(menu)
            action.setDefaultWidget(box)
            menu.addAction(action)
            box.toggled.connect(self._refresh_text)
            self._boxes[value] = box
        self._refresh_text()

    def selected_values(self) -> frozenset[object]:
        return frozenset(value for value, box in self._boxes.items() if box.isChecked())

    def _refresh_text(self) -> None:
        labels = [box.text() for box in self._boxes.values() if box.isChecked()]
        self.setText(self._all_label if len(labels) == len(self._boxes) else ", ".join(labels) or "None")
        self.selection_changed.emit()


class AutoRefreshButton(QToolButton):
    """English refresh interval menu with one active period."""

    interval_changed = Signal(int, str)

    OPTIONS = (("Off", 0), ("Every 10 seconds", 10), ("Every minute", 60))

    def __init__(self) -> None:
        super().__init__()
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self)
        menu.setTitle("Auto Refresh")
        group = QActionGroup(menu)
        group.setExclusive(True)
        for label, seconds in self.OPTIONS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setData(seconds)
            group.addAction(action)
            if seconds == 0:
                action.setChecked(True)
        group.triggered.connect(self._select_action)
        self.setMenu(menu)
        self._select_action(next(action for action in group.actions() if action.data() == 0))

    def _select_action(self, action) -> None:
        seconds = int(action.data())
        self.setText("↻" if seconds == 0 else f"↻ {seconds}s")
        self.setToolTip(f"Auto Refresh: {action.text()}")
        self.interval_changed.emit(seconds, action.text())


class FilterBar(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)

        layout.addWidget(QLabel("Exchange"))
        self.exchange = MultiSelectMenuButton(
            "All Exchanges",
            (("Bybit", "Bybit"), ("Binance", "Binance"), ("OKX", "OKX")),
            ("Bybit", "Binance", "OKX"),
        )
        layout.addWidget(self.exchange)

        layout.addWidget(QLabel("Type"))
        self.instrument = MultiSelectMenuButton(
            "Perpetual",
            (("Perpetual", InstrumentType.PERPETUAL), ("Futures", InstrumentType.FUTURES), ("Spot", InstrumentType.SPOT)),
            (InstrumentType.PERPETUAL,),
        )
        layout.addWidget(self.instrument)

        layout.addWidget(QLabel("Timeframe"))
        self.timeframe = QComboBox()
        self.timeframe.addItems(("15m", "1H", "4H", "1D", "1W", "1M"))
        layout.addWidget(self.timeframe)

        layout.addWidget(QLabel("OI"))
        self.oi_change = QComboBox()
        self.oi_change.addItem("All", None)
        for threshold in (20, 30, 50, 100):
            self.oi_change.addItem(f"> {threshold}%", ("min", threshold / 100))
        for threshold in (20, 30, 50):
            self.oi_change.addItem(f"< -{threshold}%", ("max", -threshold / 100))
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
        for signal in (SignalType.LONG_BUILDUP, SignalType.SHORT_BUILDUP, SignalType.LONG_UNWINDING, SignalType.SHORT_COVERING):
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
        self.auto_refresh = AutoRefreshButton()
        layout.addWidget(self.auto_refresh)
        layout.addStretch()

    def current_filters(self) -> ScannerFilters:
        oi_filter = self.oi_change.currentData()
        min_oi_change = max_oi_change = None
        if oi_filter:
            direction, threshold = oi_filter
            min_oi_change = threshold if direction == "min" else None
            max_oi_change = threshold if direction == "max" else None
        return ScannerFilters(
            symbol_query=self.search.text().strip(),
            exchanges=frozenset(self.exchange.selected_values()),
            instrument_types=frozenset(self.instrument.selected_values()),
            min_oi_change=min_oi_change,
            max_oi_change=max_oi_change,
            min_volume_change=self.volume_change.currentData(),
            signal=self.signal.currentData(),
        )
