from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableWidget,
)


class ScannerTable(QTableWidget):
    def __init__(self):
        super().__init__()

        headers = [
            "Symbol",
            "Exchange",
            "Type",
            "Volume",
            "OI",
            "OI %",
            "Volume %",
            "Funding %",
            "Trades",
            "Trades %",
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