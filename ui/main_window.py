from PySide6.QtCore import QSettings, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QStyle,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QApplication,
)

from scanner.filters import ScannerFilters, SignalThresholds, apply_filters
from scanner.models import ScannerItem
from scanner.scanner import ScannerService
from ui.filter_bar import FilterBar
from ui.scanner_table import ScannerTable
from ui.settings_dialog import SettingsDialog
from ui.dashboard import Dashboard
from ui.alert_journal import AlertJournal
from database.database import HistoryRepository
from ui.instrument_analysis import InstrumentAnalysisDialog
from utils.alerts import LocalAlertManager
from services.websocket_service import ConnectionStatus, WebSocketService
from services.watchlist_service import WatchlistService
from services.alert_service import AlertService
from services.license_service import LicenseService
from services.update_service import UpdateService
from services.export_service import ExportService
from telegram.telegram_bot import TelegramNotifier
from config import DATABASE_NAME
from config import REALTIME_ENABLED, REALTIME_SYMBOL_LIMIT


class RealtimeBridge(QObject):
    """Move callbacks from WebSocket threads safely into the Qt UI thread."""

    status_changed = Signal(object)
    message_received = Signal(str, object)


class ScannerWorker(QThread):
    """Load market data outside Qt's main event loop."""

    loaded = Signal(list)
    failed = Signal(str)

    def __init__(
        self,
        service: ScannerService,
        timeframe: str,
        filters: ScannerFilters,
        thresholds: SignalThresholds,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._timeframe = timeframe
        self._filters = filters
        self._thresholds = thresholds

    def run(self) -> None:
        try:
            self.loaded.emit(
                self._service.refresh(
                    self._timeframe,
                    self._filters,
                    self._thresholds,
                )
            )
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.scanner_service = ScannerService()
        self.alert_manager = LocalAlertManager()
        self.thresholds = self._load_thresholds()
        self._alerts_enabled = True
        self._alert_sound_enabled = self._load_alert_sound_enabled()
        self._refresh_worker: ScannerWorker | None = None
        self.realtime = WebSocketService()
        self.watchlist = WatchlistService(DATABASE_NAME)
        self.alert_service = AlertService()
        self.export_service = ExportService()
        self.realtime_bridge = RealtimeBridge(self)
        self.realtime.on_status = self.realtime_bridge.status_changed.emit
        self.realtime.on_message = self.realtime_bridge.message_received.emit

        self.setWindowTitle("OI Scanner Pro")
        self.resize(1600, 900)

        self.create_menu()
        self.create_toolbar()
        self.create_table()
        self.create_statusbar()
        self._create_tray_icon()

        self.filters.refresh.clicked.connect(self.refresh_data)
        self.filters.timeframe.currentTextChanged.connect(self.refresh_data)
        self.filters.oi_change.currentIndexChanged.connect(self._apply_current_filters)
        self.filters.volume_change.currentIndexChanged.connect(
            self._apply_current_filters
        )
        self.filters.signal.currentIndexChanged.connect(self._apply_current_filters)
        self.filters.exchange.currentIndexChanged.connect(self._apply_current_filters)
        self.filters.search.textChanged.connect(self._apply_current_filters)
        self.filters.watchlist_only.toggled.connect(self._apply_current_filters)
        self.table.itemDoubleClicked.connect(self._open_instrument_analysis)
        self.realtime_bridge.status_changed.connect(self._show_connection_status)
        self.realtime_bridge.message_received.connect(self._apply_realtime_message)

    def create_toolbar(self) -> None:
        toolbar = QToolBar("Scanner")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

    def create_table(self) -> None:
        central = QTabWidget()
        scanner_page = QWidget(); layout = QVBoxLayout(scanner_page)

        self.filters = FilterBar()
        layout.addWidget(self.filters)

        self.table = ScannerTable()
        layout.addWidget(self.table)

        self.dashboard = Dashboard()
        central.addTab(scanner_page, "Scanner")
        central.addTab(self.dashboard, "Dashboard")
        self.alert_journal = AlertJournal(HistoryRepository(DATABASE_NAME))
        central.addTab(self.alert_journal, "Alerts")
        self.setCentralWidget(central)

    def create_statusbar(self) -> None:
        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

    def create_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        file_menu.addAction("Export CSV").triggered.connect(lambda: self._export("csv"))
        file_menu.addAction("Export Excel").triggered.connect(lambda: self._export("xlsx"))
        file_menu.addAction("Export JSON").triggered.connect(lambda: self._export("json"))
        menu.addMenu("Scanner")

        alerts_menu = menu.addMenu("Alerts")
        self.alerts_action = alerts_menu.addAction("Enable local alerts")
        self.alerts_action.setCheckable(True)
        self.alerts_action.setChecked(True)
        self.alerts_action.toggled.connect(self._set_alerts_enabled)
        self.alert_sound_action = alerts_menu.addAction("Play sound for alerts")
        self.alert_sound_action.setCheckable(True)
        self.alert_sound_action.setChecked(self._alert_sound_enabled)
        self.alert_sound_action.toggled.connect(self._set_alert_sound_enabled)

        settings_menu = menu.addMenu("Settings")
        settings_action = settings_menu.addAction("Signal thresholds...")
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction("Check license").triggered.connect(self._check_license)
        settings_menu.addAction("Check updates").triggered.connect(self._check_updates)

        watchlist_menu = menu.addMenu("Watchlist")
        watchlist_menu.addAction("Add selected instrument").triggered.connect(self._add_selected_to_watchlist)
        watchlist_menu.addAction("Remove selected instrument").triggered.connect(self._remove_selected_from_watchlist)

        menu.addMenu("Help")

    def refresh_data(self, _timeframe: str | None = None) -> None:
        """Request Bybit data without blocking the interface."""
        if self._refresh_worker is not None:
            return

        self.filters.refresh.setEnabled(False)
        self.filters.timeframe.setEnabled(False)
        timeframe = self.filters.timeframe.currentText()
        self.statusBar().showMessage(
            f"Loading perpetual market data ({timeframe})..."
        )

        worker = ScannerWorker(
            self.scanner_service,
            timeframe,
            self.filters.current_filters(),
            self.thresholds,
            self,
        )
        worker.loaded.connect(self._show_items)
        worker.failed.connect(self._show_refresh_error)
        worker.finished.connect(self._finish_refresh)
        self._refresh_worker = worker
        worker.start()

    def _show_items(self, _items: list[ScannerItem]) -> None:
        visible_items = apply_filters(
            self.scanner_service.last_refreshed_items,
            self.filters.current_filters(),
        )
        visible_items = self._apply_watchlist_filter(visible_items)
        self.table.set_items(visible_items)
        self.dashboard.set_items(self.scanner_service.last_refreshed_items)
        self.dashboard.set_watchlist(self.scanner_service.last_refreshed_items, self.watchlist.all())
        self._start_realtime(self.scanner_service.last_refreshed_items)
        alerts = self._show_alerts()
        timeframe = self.filters.timeframe.currentText()
        self.statusBar().showMessage(
            f"Updated {len(visible_items)} perpetual markets ({timeframe}) | "
            f"{self.scanner_service.last_history_status.message} | "
            f"Alerts: {len(alerts)}"
        )

    def _apply_current_filters(self, _value: object) -> None:
        """Filter the latest refresh locally without another Bybit request."""
        if not self.scanner_service.last_refreshed_items:
            return
        self.table.set_items(
            self._apply_watchlist_filter(apply_filters(
                self.scanner_service.last_refreshed_items,
                self.filters.current_filters(),
            ))
        )

    def _apply_watchlist_filter(self, items: list[ScannerItem]) -> list[ScannerItem]:
        if not self.filters.watchlist_only.isChecked():
            return items
        watchlist = self.watchlist.all()
        return [item for item in items if (item.exchange, item.symbol) in watchlist]

    def _open_instrument_analysis(self, _cell) -> None:
        item = self.table.selected_scanner_item()
        if item is not None:
            InstrumentAnalysisDialog(item, self).exec()

    def _show_alerts(self):
        if not self._alerts_enabled:
            return []

        alerts = self.alert_manager.collect(
            self.scanner_service.last_refreshed_items,
            self.thresholds,
        )
        for alert in alerts:
            self.alert_service.record(alert.symbol, "Scanner", alert.message)
        if alerts:
            self.alert_journal.reload()
            if self._alert_sound_enabled:
                QApplication.beep()
            settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
            TelegramNotifier(str(settings.value("telegram/token", "")), str(settings.value("telegram/chat_id", ""))).send(alert.message)
        if self._tray_icon.isVisible():
            for alert in alerts[:3]:
                self._tray_icon.showMessage(
                    "OI Scanner Pro",
                    alert.message,
                    QSystemTrayIcon.MessageIcon.Information,
                    10_000,
                )
        return alerts

    def _show_refresh_error(self, message: str) -> None:
        self.statusBar().showMessage(f"Bybit update failed: {message}")

    def _apply_realtime_message(self, exchange: str, payload: dict) -> None:
        """Apply normalized ticker data received from an exchange WebSocket."""
        if exchange == "Bybit":
            from api.bybit import BybitClient

            liquidations = BybitClient.parse_liquidation_message(payload)
            if liquidations:
                HistoryRepository(DATABASE_NAME).save_liquidations(liquidations)
                return
        update = self._parse_realtime_payload(exchange, payload)
        if update is None:
            return
        item = self.scanner_service.apply_live_update(exchange, update)
        if item is not None:
            self.table.update_item(item)

    @staticmethod
    def _parse_realtime_payload(exchange: str, payload: dict) -> dict | None:
        if exchange == "Bybit":
            from api.bybit import BybitClient
            return BybitClient.parse_ticker_message(payload)
        if exchange == "Binance":
            from api.binance import BinanceClient
            return BinanceClient.parse_ticker_message(payload)
        if exchange == "OKX":
            data = payload.get("data", [])
            if not data or not isinstance(data[0], dict):
                return None
            ticker = data[0]
            return {"symbol": ticker.get("instId"), "lastPrice": ticker.get("last"), "turnover24h": ticker.get("volCcy24h")}
        return None

    def _show_connection_status(self, status: ConnectionStatus) -> None:
        state = "Connected" if status.connected else "Disconnected"
        last_update = status.last_update.strftime("%H:%M:%S") if status.last_update else "—"
        ping = f"{status.ping_ms:.0f} ms" if status.ping_ms is not None else "—"
        self.statusBar().showMessage(f"{status.exchange}: {state} | Last Update: {last_update} | Ping: {ping}")

    def _start_realtime(self, items: list[ScannerItem]) -> None:
        if not REALTIME_ENABLED:
            return
        grouped: dict[str, list[str]] = {}
        for item in items:
            grouped.setdefault(item.exchange, []).append(item.symbol)
        for exchange, symbols in grouped.items():
            symbols = list(dict.fromkeys(symbols))[:REALTIME_SYMBOL_LIMIT]
            if exchange == "Bybit":
                from api.bybit import BybitClient
                subscription = BybitClient.ticker_subscription(symbols)
                subscription["args"].extend(BybitClient.liquidation_topics(symbols))
                self.realtime.start(exchange, BybitClient.WEBSOCKET_URL, subscription)
            elif exchange == "Binance":
                from api.binance import BinanceClient
                self.realtime.start(exchange, BinanceClient.ticker_stream_url(symbols), None)
            elif exchange == "OKX":
                from api.okx import OKXClient
                self.realtime.start(exchange, OKXClient.WEBSOCKET_URL, OKXClient.ticker_subscription(symbols))

    def _add_selected_to_watchlist(self) -> None:
        item = self.table.selected_scanner_item()
        if item is not None:
            self.watchlist.add(item.exchange, item.symbol)
            self.dashboard.set_watchlist(self.scanner_service.last_refreshed_items, self.watchlist.all())

    def _remove_selected_from_watchlist(self) -> None:
        item = self.table.selected_scanner_item()
        if item is not None:
            self.watchlist.remove(item.exchange, item.symbol)
            self.dashboard.set_watchlist(self.scanner_service.last_refreshed_items, self.watchlist.all())

    def _export(self, extension: str) -> None:
        items = self.scanner_service.last_refreshed_items
        if not items:
            self.statusBar().showMessage("Nothing to export")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export scanner", f"scanner.{extension}", f"*.{extension}")
        if not path:
            return
        try:
            {"csv": self.export_service.export_csv, "xlsx": self.export_service.export_excel, "json": self.export_service.export_json}[extension](items, path)
            self.statusBar().showMessage(f"Exported {len(items)} instruments")
        except Exception as error:
            QMessageBox.warning(self, "Export failed", str(error))

    def closeEvent(self, event) -> None:
        self.realtime.stop()
        event.accept()

    def _finish_refresh(self) -> None:
        self.filters.refresh.setEnabled(True)
        self.filters.timeframe.setEnabled(True)
        self._refresh_worker = None

    def _create_tray_icon(self) -> None:
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.show()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.thresholds, self)
        if dialog.exec():
            self.thresholds = dialog.thresholds()
            self._save_thresholds()
            settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
            for key, value in dialog.external_settings().items():
                settings.setValue(key, value)

    def _set_alerts_enabled(self, enabled: bool) -> None:
        self._alerts_enabled = enabled

    def _set_alert_sound_enabled(self, enabled: bool) -> None:
        self._alert_sound_enabled = enabled
        QSettings("OI Scanner Pro", "OI Scanner Pro").setValue("alerts/sound", enabled)

    @staticmethod
    def _load_alert_sound_enabled() -> bool:
        return str(QSettings("OI Scanner Pro", "OI Scanner Pro").value("alerts/sound", "true")).lower() != "false"

    def _load_thresholds(self) -> SignalThresholds:
        settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
        return SignalThresholds(
            alert_oi_change=float(settings.value("alerts/oi", 0.20)),
            alert_volume_change=float(settings.value("alerts/volume", 0.20)),
            alert_funding_rate=float(settings.value("alerts/funding", 0.0001)),
            alert_score=int(settings.value("alerts/score", 6)),
        )

    def _save_thresholds(self) -> None:
        settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
        settings.setValue("alerts/oi", self.thresholds.alert_oi_change)
        settings.setValue("alerts/volume", self.thresholds.alert_volume_change)
        settings.setValue("alerts/funding", self.thresholds.alert_funding_rate)
        settings.setValue("alerts/score", self.thresholds.alert_score)

    def _check_license(self) -> None:
        settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
        valid = LicenseService(str(settings.value("license/url", ""))).validate(str(settings.value("license/key", "")))
        self.statusBar().showMessage("License valid" if valid else "License is not configured or invalid")

    def _check_updates(self) -> None:
        settings = QSettings("OI Scanner Pro", "OI Scanner Pro")
        version = UpdateService(str(settings.value("updates/url", ""))).latest_version()
        self.statusBar().showMessage(f"Latest version: {version}" if version else "Update service is not configured")
