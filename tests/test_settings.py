"""Tests for portable application configuration."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from utils.settings import application_settings


class ApplicationSettingsTests(TestCase):
    def test_persists_values_in_an_ini_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings.ini"
            settings = application_settings(path)
            settings.setValue("alerts/enabled", False)
            settings.setValue("telegram/chat_id", "123")
            settings.sync()

            restored = application_settings(path)
            self.assertEqual(str(restored.value("alerts/enabled")).lower(), "false")
            self.assertEqual(restored.value("telegram/chat_id"), "123")
