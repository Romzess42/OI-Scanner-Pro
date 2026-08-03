"""Read-only terminal view of persistent scanner alerts."""
from __future__ import annotations
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem
from database.database import HistoryRepository

class AlertJournal(QTableWidget):
    def __init__(self, repository: HistoryRepository):
        super().__init__(0,4); self.repository=repository; self.setHorizontalHeaderLabels(["Time","Exchange","Symbol","Message"]); self.reload()
    def reload(self):
        rows=self.repository.get_alerts()
        self.setRowCount(len(rows))
        for index,row in enumerate(rows):
            for column,key in enumerate(("timestamp_ms","exchange","symbol","message")):
                value=row[key]
                self.setItem(index,column,QTableWidgetItem(str(value)))
