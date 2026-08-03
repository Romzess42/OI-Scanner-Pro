"""Deduplicated local alerts for significant scanner signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import ALERT_COOLDOWN_SECONDS
from scanner.filters import SignalThresholds
from scanner.models import ScannerItem, SignalType


@dataclass(frozen=True, slots=True)
class LocalAlert:
    """A single local desktop alert."""

    symbol: str
    signal: SignalType
    message: str


class LocalAlertManager:
    """Prevent repeated local alerts for the same symbol and signal."""

    def __init__(self, cooldown_seconds: int = ALERT_COOLDOWN_SECONDS):
        self._cooldown = timedelta(seconds=cooldown_seconds)
        self._last_sent: dict[tuple[str, SignalType], datetime] = {}

    def collect(
        self,
        items: list[ScannerItem],
        thresholds: SignalThresholds,
        now: datetime | None = None,
    ) -> list[LocalAlert]:
        """Return new alerts that exceed OI and volume alert thresholds."""
        current_time = now or datetime.now(timezone.utc)
        alerts: list[LocalAlert] = []

        for item in items:
            if not self._is_eligible(item, thresholds):
                continue

            key = (item.symbol, item.signal)
            previous_time = self._last_sent.get(key)
            if previous_time and current_time - previous_time < self._cooldown:
                continue

            self._last_sent[key] = current_time
            alerts.append(
                LocalAlert(
                    symbol=item.symbol,
                    signal=item.signal,
                    message=self._format_message(item, thresholds),
                )
            )

        return alerts

    @staticmethod
    def _is_eligible(item: ScannerItem, thresholds: SignalThresholds) -> bool:
        return (
            item.signal not in (SignalType.NONE, SignalType.NEUTRAL)
            and item.oi_change_pct is not None
            and abs(item.oi_change_pct) >= thresholds.alert_oi_change
            and item.volume_change_pct is not None
            and abs(item.volume_change_pct) >= thresholds.alert_volume_change
        )

    @staticmethod
    def _format_message(item: ScannerItem, thresholds: SignalThresholds) -> str:
        lines = [
            item.symbol,
            f"OI {item.oi_change_pct * 100:+.2f}%",
            f"Volume {item.volume_change_pct * 100:+.2f}%",
            item.signal.value,
        ]
        if (
            item.funding_rate is not None
            and abs(item.funding_rate) >= thresholds.alert_funding_rate
        ):
            lines.insert(3, f"Funding {item.funding_rate * 100:+.3f}%")
        return "\n".join(lines)
