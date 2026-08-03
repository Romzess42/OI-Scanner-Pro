"""Dedicated ranking service used by the scanner and future dashboard."""

from scanner.filters import SignalThresholds, calculate_score
from scanner.models import ScannerItem


class ScoreService:
    """Calculate and rank normalized scanner items by their score."""

    def score(self, item: ScannerItem, thresholds: SignalThresholds) -> int:
        return calculate_score(item, thresholds)

    def rank(
        self, items: list[ScannerItem], thresholds: SignalThresholds
    ) -> list[ScannerItem]:
        from dataclasses import replace

        return sorted(
            (replace(item, score=self.score(item, thresholds)) for item in items),
            key=lambda item: item.score,
            reverse=True,
        )

    def top_twenty(
        self, items: list[ScannerItem], thresholds: SignalThresholds
    ) -> list[ScannerItem]:
        return self.rank(items, thresholds)[:20]
