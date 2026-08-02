from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidgetItem,
    QTableWidget,
)

from scanner.models import ScannerItem


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
            "Price",
        ]

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)

        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.verticalHeader().setVisible(False)

        header = self.horizontalHeader()

        header.setStretchLastSection(True)

        header.setSectionsMovable(True)

        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header.customContextMenuRequested.connect(
            self.show_header_menu
        )

        for i in range(self.columnCount()):
            header.setSectionResizeMode(
                i,
                QHeaderView.ResizeMode.Interactive,
            )

    def show_header_menu(self, pos):

        menu = QMenu()

        header = self.horizontalHeader()

        for index in range(self.columnCount()):

            action = menu.addAction(
                self.horizontalHeaderItem(index).text()
            )

            action.setCheckable(True)

            action.setChecked(not self.isColumnHidden(index))

            action.triggered.connect(
                lambda checked, i=index: self.setColumnHidden(
                    i,
                    not checked,
                )
            )

        menu.exec(header.mapToGlobal(pos))

    def set_items(self, items: list[ScannerItem]) -> None:
        """Replace table rows with the latest normalized scanner data."""
        sorting_enabled = self.isSortingEnabled()
        self.setSortingEnabled(False)
        self.setRowCount(len(items))

        for row, item in enumerate(items):
            values = [
                item.symbol,
                item.exchange,
                item.instrument_type,
                self._format_compact_number(item.volume_24h),
                self._format_compact_number(item.open_interest),
                "—",
                "—",
                self._format_percent(item.funding_rate, decimals=3),
                "—",
                "—",
                self._format_percent(item.price_change_pct, decimals=2),
                self._format_price(item.price),
            ]

            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column >= 3:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter
                    )
                self.setItem(row, column, cell)

        self.setSortingEnabled(sorting_enabled)

    @staticmethod
    def _format_compact_number(value: float | None) -> str:
        if value is None:
            return "—"

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
            return "—"

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
            return "—"
        return f"{value * 100:.{decimals}f}".rstrip("0").rstrip(".") + "%"
