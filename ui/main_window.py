from ui.filter_bar import FilterBar
from ui.scanner_table import ScannerTable

from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("OI Scanner Pro")
        self.resize(1600, 900)

        self.create_menu()
        self.create_toolbar()
        self.create_table()
        self.create_statusbar()

    def create_toolbar(self):
        toolbar = QToolBar("Scanner")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

    def create_table(self):
        central = QWidget()

        layout = QVBoxLayout()

        self.filters = FilterBar()
        layout.addWidget(self.filters)

        self.table = ScannerTable()
        layout.addWidget(self.table)

        central.setLayout(layout)

        self.setCentralWidget(central)

    def create_statusbar(self):
        status = QStatusBar()
        status.showMessage("Ready")

        self.setStatusBar(status)

    def create_menu(self):
        menu = self.menuBar()

        menu.addMenu("File")
        menu.addMenu("Scanner")
        menu.addMenu("Alerts")
        menu.addMenu("Settings")
        menu.addMenu("Help")