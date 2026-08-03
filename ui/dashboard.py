"""Compact dashboard derived from the latest normalized scanner items."""
from __future__ import annotations
from PySide6.QtWidgets import QGridLayout, QLabel, QListWidget, QWidget
from scanner.models import ScannerItem

class Dashboard(QWidget):
    def __init__(self):
        super().__init__(); self._lists={}; layout=QGridLayout(self)
        for index, (title, key, reverse) in enumerate((("Top OI Gainers","oi_change_pct",True),("Top OI Losers","oi_change_pct",False),("Top Volume","volume_24h",True),("Top Funding","funding_rate",True),("Highest Score","score",True))):
            box=QListWidget(); layout.addWidget(QLabel(title),index//2,(index%2)*2); layout.addWidget(box,index//2,(index%2)*2+1); self._lists[title]=(box,key,reverse)
    def set_items(self, items: list[ScannerItem]):
        for box,key,reverse in self._lists.values():
            box.clear()
            for item in sorted(items,key=lambda value:getattr(value,key) or 0,reverse=reverse)[:20]: box.addItem(f"{item.symbol}  {item.exchange}  {getattr(item,key) or 0:.4g}")

    def set_watchlist(self, items: list[ScannerItem], watchlist: set[tuple[str, str]]):
        title = "Watchlist"
        if title not in self._lists:
            box=QListWidget(); position=len(self._lists); self.layout().addWidget(QLabel(title),position//2,(position%2)*2); self.layout().addWidget(box,position//2,(position%2)*2+1); self._lists[title]=(box,"score",True)
        box, _, _ = self._lists[title]; box.clear()
        for item in items:
            if (item.exchange,item.symbol) in watchlist: box.addItem(f"{item.symbol}  {item.exchange}  Score {item.score}")
