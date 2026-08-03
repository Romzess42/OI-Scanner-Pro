from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)

from scanner.models import ScannerItem, SignalType


DASH = "\u2014"
PRICE_COLUMN = 13


class SortableTableWidgetItem(QTableWidgetItem):
    """A table item that sorts by raw values instead of formatted text."""

    def __init__(self, text: str, sort_value: float | int | str):
        super().__init__(text)
        self._sort_value = sort_value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableWidgetItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


class ScannerTable(QTableWidget):
    def __init__(self):
        super().__init__()

        headers = [
            "Symbol",
            "Exchange",
            "Type",
            "Volume $",
            "OI",
            "OI %",
            "Volume %",
            "Funding %",
            "Trades",
            "Trades %",
            "Price Chg %",
            "Signal",
            "Score",
            "Price",
        ]

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setColumnHidden(headers.index("Trades"), True)
        self.setColumnHidden(headers.index("Trades %"), True)

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_menu)

        for index in range(self.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Interactive)

    def show_header_menu(self, pos) -> None:
        menu = QMenu()
        header = self.horizontalHeader()

        for index in range(self.columnCount()):
            action = menu.addAction(self.horizontalHeaderItem(index).text())
            action.setCheckable(True)
            action.setChecked(not self.isColumnHidden(index))
            action.triggered.connect(
                lambda checked, column=index: self.setColumnHidden(
                    column,
                    not checked,
                )
            )

        menu.exec(header.mapToGlobal(pos))

    def set_items(self, items: list[ScannerItem]) -> None:
        self._items = items
        """Replace table rows with the latest normalized scanner data."""
        sorting_enabled = self.isSortingEnabled()
        self.setSortingEnabled(False)
        self.setRowCount(len(items))

        for row, item in enumerate(items):
            values = [
                (item.symbol, item.symbol),
                (item.exchange, item.exchange),
                (item.instrument_type, item.instrument_type),
                (
                    self._format_compact_number(item.volume_24h),
                    self._sort_value(item.volume_24h),
                ),
                (
                    DASH if item.instrument_type == "USDT Spot" else self._format_compact_number(item.open_interest),
                    self._sort_value(item.open_interest),
                ),
                (
                    DASH if item.instrument_type == "USDT Spot" else self._format_history_percent(item.oi_change_pct),
                    self._sort_value(item.oi_change_pct),
                ),
                (
                    self._format_history_percent(item.volume_change_pct),
                    self._sort_value(item.volume_change_pct),
                ),
                (
                    DASH if item.instrument_type == "USDT Spot" else self._format_percent(item.funding_rate, decimals=3),
                    self._sort_value(item.funding_rate),
                ),
                (DASH, float("-inf")),
                (DASH, float("-inf")),
                (
                    self._format_history_percent(item.price_change_pct),
                    self._sort_value(item.price_change_pct),
                ),
                (
                    self._format_signal(item.signal),
                    self._signal_sort_value(item.signal),
                ),
                (str(item.score), item.score),
                (self._format_price(item.price), self._sort_value(item.price)),
            ]

            for column, (text, sort_value) in enumerate(values):
                cell = SortableTableWidgetItem(text, sort_value)
                if column >= 3:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                if column == 5:
                    self._apply_oi_change_style(cell, item.oi_change_pct)
                if column == 11:
                    self._apply_signal_style(cell, item.signal)
                self.setItem(row, column, cell)

        self.setSortingEnabled(sorting_enabled)

    def selected_scanner_item(self) -> ScannerItem | None:
        row = self.currentRow()
        return self._items[row] if 0 <= row < len(getattr(self, "_items", [])) else None

    def update_item(self, changed: ScannerItem) -> None:
        """Refresh the one visible row changed by a WebSocket ticker event."""
        for index, item in enumerate(getattr(self, "_items", [])):
            if item.exchange == changed.exchange and item.symbol == changed.symbol:
                self._items[index] = changed
                for row in range(self.rowCount()):
                    symbol_cell = self.item(row, 0)
                    exchange_cell = self.item(row, 1)
                    if symbol_cell is None or exchange_cell is None:
                        continue
                    if symbol_cell.text() == changed.symbol and exchange_cell.text() == changed.exchange:
                        self._replace_live_cell(row, 3, self._format_compact_number(changed.volume_24h), changed.volume_24h)
                        self._replace_live_cell(row, 4, self._format_compact_number(changed.open_interest), changed.open_interest)
                        self._replace_live_cell(row, 7, self._format_percent(changed.funding_rate, 3), changed.funding_rate)
                        self._replace_live_cell(row, PRICE_COLUMN, self._format_price(changed.price), changed.price)
                        break
                return

    def _replace_live_cell(self, row: int, column: int, text: str, value: float | None) -> None:
        cell = self.item(row, column)
        if cell is None:
            cell = SortableTableWidgetItem(text, self._sort_value(value))
            cell.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.setItem(row, column, cell)
            return
        cell.setText(text)
        if isinstance(cell, SortableTableWidgetItem):
            cell._sort_value = self._sort_value(value)

    @staticmethod
    def _format_compact_number(value: float | None) -> str:
        if value is None:
            return DASH

        for threshold, suffix in (
            (1_000_000_000, "B"),
            (1_000_000, "M"),
            (1_000, "K"),
        ):
            if abs(value) >= threshold:
                return f"{value / threshold:.2f}".rstrip("0").rstrip(".") + suffix

        return f"{value:,.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_price(value: float | None) -> str:
        if value is None:
            return DASH

        magnitude = abs(value)
        if magnitude >= 10_000:
            decimals = 1
        elif magnitude >= 100:
            decimals = 2
        elif magnitude >= 1:
            decimals = 3
        else:
            decimals = 5

        return f"{value:,.{decimals}f}".rstrip("0").rstrip(".")

    @staticmethod
    def _format_percent(value: float | None, decimals: int) -> str:
        if value is None:
            return DASH
        return f"{value * 100:.{decimals}f}".rstrip("0").rstrip(".") + "%"

    @staticmethod
    def _format_history_percent(value: float | None) -> str:
        if value is None:
            return "Collecting..."
        return ScannerTable._format_percent(value, decimals=2)

    @staticmethod
    def _format_signal(signal: SignalType) -> str:
        return signal.value or DASH

    @staticmethod
    def _sort_value(value: float | None) -> float:
        return value if value is not None else float("-inf")

    @staticmethod
    def _signal_sort_value(signal: SignalType) -> int:
        return {
            SignalType.LONG_BUILDUP: 4,
            SignalType.SHORT_BUILDUP: 3,
            SignalType.LONG_UNWINDING: 2,
            SignalType.SHORT_COVERING: 1,
            SignalType.NEUTRAL: 0,
            SignalType.NONE: 0,
        }[signal]

    @staticmethod
    def _apply_oi_change_style(
        cell: QTableWidgetItem,
        value: float | None,
    ) -> None:
        if value is None:
            return
        if value > 0.10:
            cell.setBackground(QColor("#1B5E20"))
            cell.setForeground(QColor("#FFFFFF"))
        elif value < -0.10:
            cell.setBackground(QColor("#B71C1C"))
            cell.setForeground(QColor("#FFFFFF"))

    @staticmethod
    def _apply_signal_style(cell: QTableWidgetItem, signal: SignalType) -> None:
        if signal == SignalType.LONG_BUILDUP:
            cell.setBackground(QColor("#1B5E20"))
            cell.setForeground(QColor("#FFFFFF"))
        elif signal == SignalType.SHORT_BUILDUP:
            cell.setBackground(QColor("#B71C1C"))
            cell.setForeground(QColor("#FFFFFF"))
        elif signal == SignalType.LONG_UNWINDING:
            cell.setBackground(QColor("#F9A825"))
            cell.setForeground(QColor("#1F1F1F"))
        elif signal == SignalType.SHORT_COVERING:
            cell.setBackground(QColor("#1565C0"))
            cell.setForeground(QColor("#FFFFFF"))
