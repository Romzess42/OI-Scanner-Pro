"""Tests for menu-driven automatic refresh controls."""

from __future__ import annotations

import os
from unittest import TestCase

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.filter_bar import AutoRefreshButton, FilterBar


class AutoRefreshTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_auto_refresh_menu_emits_selected_interval(self):
        button = AutoRefreshButton()
        selected: list[tuple[int, str]] = []
        button.interval_changed.connect(lambda seconds, label: selected.append((seconds, label)))

        action = next(action for action in button.menu().actions() if action.data() == 10)
        action.trigger()

        self.assertEqual(selected[-1], (10, "Every 10 seconds"))
        self.assertEqual(button.text(), "↻ 10s")
        self.assertIn("Every 10 seconds", button.toolTip())

    def test_filter_bar_returns_multiple_exchange_and_type_values(self):
        bar = FilterBar()
        bar.exchange._boxes["Bybit"].setChecked(False)
        bar.instrument._boxes[next(value for value in bar.instrument._boxes if value.value == "Spot")].setChecked(True)

        filters = bar.current_filters()

        self.assertEqual(filters.exchanges, frozenset(("Binance", "OKX")))
        self.assertEqual({value.value for value in filters.instrument_types}, {"Perpetual", "Spot"})
