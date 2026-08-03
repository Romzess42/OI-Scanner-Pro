"""External v1.0 services must fail safely when servers are unavailable."""

from unittest import TestCase
from datetime import datetime, timezone
from tempfile import TemporaryDirectory

from services.license_service import LicenseService
from services.update_service import UpdateService
from telegram.telegram_bot import TelegramNotifier
from services.export_service import ExportService
from scanner.models import ScannerItem


class ExternalServiceTests(TestCase):
    def test_unconfigured_services_do_not_make_requests(self):
        self.assertFalse(LicenseService().validate("key"))
        self.assertIsNone(UpdateService().latest_version())

    def test_invalid_urls_fail_without_breaking_the_application(self):
        self.assertFalse(LicenseService("http://127.0.0.1:1").validate("key"))
        self.assertIsNone(UpdateService("http://127.0.0.1:1").latest_version())

    def test_telegram_is_opt_in_and_network_failure_is_safe(self):
        self.assertFalse(TelegramNotifier().enabled)
        self.assertFalse(TelegramNotifier().send("scanner alert"))
        self.assertFalse(TelegramNotifier("token", "1").send("scanner alert"))

    def test_export_writes_csv_json_and_excel_files(self):
        item = ScannerItem("BTCUSDT", "Bybit", "USDT Perpetual", 1.0, 2.0, 3.0, None, None, None, None, None, datetime.now(timezone.utc))
        with TemporaryDirectory() as directory:
            service = ExportService()
            for extension, method in (("csv", service.export_csv), ("json", service.export_json), ("xlsx", service.export_excel)):
                path = f"{directory}/scanner.{extension}"
                method([item], path)
                from pathlib import Path
                self.assertTrue(Path(path).is_file())
                self.assertGreater(Path(path).stat().st_size, 0)
