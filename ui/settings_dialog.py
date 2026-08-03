"""Settings dialog for scanner alert thresholds."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QLineEdit,
)

from scanner.filters import SignalThresholds
from utils.settings import application_settings


class SettingsDialog(QDialog):
    """Edit threshold settings and expose them as domain values."""

    def __init__(self, thresholds: SignalThresholds, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scanner Settings")

        layout = QFormLayout(self)
        self.oi_threshold = self._create_percent_box(
            thresholds.alert_oi_change * 100
        )
        self.volume_threshold = self._create_percent_box(
            thresholds.alert_volume_change * 100
        )
        self.funding_threshold = self._create_percent_box(
            thresholds.alert_funding_rate * 100,
            decimals=3,
        )
        self.score_threshold = QSpinBox()
        self.score_threshold.setRange(0, 100)
        self.score_threshold.setValue(thresholds.alert_score)

        layout.addRow("Alert OI threshold", self.oi_threshold)
        layout.addRow("Alert Volume threshold", self.volume_threshold)
        layout.addRow("Funding threshold", self.funding_threshold)
        layout.addRow("Minimum Score for alert", self.score_threshold)
        self.telegram_token = QLineEdit()
        self.telegram_chat_id = QLineEdit()
        self.license_key = QLineEdit()
        self.license_url = QLineEdit()
        self.update_url = QLineEdit()
        self.telegram_token.setEchoMode(QLineEdit.EchoMode.Password)
        settings = application_settings()
        self.telegram_token.setText(str(settings.value("telegram/token", "")))
        self.telegram_chat_id.setText(str(settings.value("telegram/chat_id", "")))
        self.license_key.setText(str(settings.value("license/key", "")))
        self.license_url.setText(str(settings.value("license/url", "")))
        self.update_url.setText(str(settings.value("updates/url", "")))
        layout.addRow("Telegram bot token", self.telegram_token)
        layout.addRow("Telegram chat ID", self.telegram_chat_id)
        layout.addRow("License key", self.license_key)
        layout.addRow("License validation URL", self.license_url)
        layout.addRow("Update manifest URL", self.update_url)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def thresholds(self) -> SignalThresholds:
        return SignalThresholds(
            alert_oi_change=self.oi_threshold.value() / 100,
            alert_volume_change=self.volume_threshold.value() / 100,
            alert_funding_rate=self.funding_threshold.value() / 100,
            alert_score=self.score_threshold.value(),
        )

    def external_settings(self) -> dict[str, str]:
        return {"telegram/token": self.telegram_token.text().strip(), "telegram/chat_id": self.telegram_chat_id.text().strip(), "license/key": self.license_key.text().strip(), "license/url": self.license_url.text().strip(), "updates/url": self.update_url.text().strip()}

    @staticmethod
    def _create_percent_box(value: float, decimals: int = 1) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setRange(0, 1000)
        box.setDecimals(decimals)
        box.setSingleStep(1 if decimals <= 1 else 0.001)
        box.setSuffix("%")
        box.setValue(value)
        return box
