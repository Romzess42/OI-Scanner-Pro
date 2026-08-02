from ui.filter_bar import FilterBar
from ui.scanner_table import ScannerTable

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from scanner.models import ScannerItem
from scanner.scanner import ScannerService


class ScannerWorker(QThread):
    """Load market data outside Qt's main event loop."""

    loaded = Signal(list)
    failed = Signal(str)

    def __init__(self, service: ScannerService, timeframe: str, parent=None):
        super().__init__(parent)
        self._service = service
        self._timeframe = timeframe

    def run(self) -> None:
        try:
            self.loaded.emit(self._service.refresh(self._timeframe))
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.scanner_service = ScannerService()
        self._refresh_worker: ScannerWorker | None = None

        self.setWindowTitle("OI Scanner Pro")
        self.resize(1600, 900)

        self.create_menu()
        self.create_toolbar()
        self.create_table()
        self.create_statusbar()

        self.filters.refresh.clicked.connect(self.refresh_data)
        self.filters.timeframe.currentTextChanged.connect(self.refresh_data)

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

    def refresh_data(self, _timeframe: str | None = None) -> None:
        """Request the latest Bybit data without blocking the interface."""
        if self._refresh_worker is not None:
            return

        self.filters.refresh.setEnabled(False)
        self.filters.timeframe.setEnabled(False)
        timeframe = self.filters.timeframe.currentText()
        self.statusBar().showMessage(
            f"Loading Bybit USDT perpetual data ({timeframe})…"
        )

        worker = ScannerWorker(self.scanner_service, timeframe, self)
        worker.loaded.connect(self._show_items)
        worker.failed.connect(self._show_refresh_error)
        worker.finished.connect(self._finish_refresh)
        self._refresh_worker = worker
        worker.start()

    def _show_items(self, items: list[ScannerItem]) -> None:
        self.table.set_items(items)
        timeframe = self.filters.timeframe.currentText()
        self.statusBar().showMessage(
            f"Updated {len(items)} Bybit USDT perpetuals ({timeframe})"
        )

    def _show_refresh_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Bybit update failed: {message}")

    def _finish_refresh(self) -> None:
        self.filters.refresh.setEnabled(True)
        self.filters.timeframe.setEnabled(True)
        self._refresh_worker = None
