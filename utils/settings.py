"""Portable local settings storage for OI Scanner Pro."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings


def application_settings(path: str | Path | None = None) -> QSettings:
    """Return the application's INI settings store.

    Keeping the file next to the local SQLite database makes settings portable
    and avoids depending on a Windows Registry policy.  The file is ignored by
    Git because it can contain a user's Telegram token and license key.
    """
    filename = Path(path) if path is not None else Path(__file__).resolve().parents[1] / "oi_scanner.ini"
    return QSettings(str(filename), QSettings.Format.IniFormat)
