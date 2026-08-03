"""Export normalized scanner rows without coupling exports to the UI."""
from __future__ import annotations
import csv
import json
from dataclasses import asdict
from pathlib import Path
from scanner.models import ScannerItem

class ExportService:
    def export_json(self, items: list[ScannerItem], path: str | Path) -> None:
        Path(path).write_text(json.dumps([self._row(item) for item in items], indent=2), encoding="utf-8")
    def export_csv(self, items: list[ScannerItem], path: str | Path) -> None:
        rows = [self._row(item) for item in items]
        with Path(path).open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]) if rows else ["symbol"])
            writer.writeheader(); writer.writerows(rows)
    def export_excel(self, items: list[ScannerItem], path: str | Path) -> None:
        import pandas as pd
        pd.DataFrame([self._row(item) for item in items]).to_excel(path, index=False)
    @staticmethod
    def _row(item: ScannerItem) -> dict:
        row = asdict(item); row["updated_at"] = item.updated_at.isoformat(); row["signal"] = item.signal.value; return row
