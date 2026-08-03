"""Signal detection, scoring and in-memory scanner filters."""

from __future__ import annotations

from dataclasses import dataclass

from config import (
    DEFAULT_ALERT_FUNDING_THRESHOLD,
    DEFAULT_ALERT_OI_THRESHOLD,
    DEFAULT_ALERT_SCORE_THRESHOLD,
    DEFAULT_ALERT_VOLUME_THRESHOLD,
)
from scanner.models import InstrumentType, ScannerItem, SignalType


@dataclass(frozen=True, slots=True)
class ScannerFilters:
    """Optional thresholds that restrict the rows visible in the scanner."""

    symbol_query: str = ""
    exchange: str | None = None
    exchanges: frozenset[str] | None = None
    instrument_types: frozenset[InstrumentType] | None = None
    min_oi_change: float | None = None
    max_oi_change: float | None = None
    min_volume_change: float | None = None
    signal: SignalType | None = None


@dataclass(frozen=True, slots=True)
class SignalThresholds:
    """User-configurable alert and score thresholds, stored as decimal values."""

    alert_oi_change: float = DEFAULT_ALERT_OI_THRESHOLD
    alert_volume_change: float = DEFAULT_ALERT_VOLUME_THRESHOLD
    alert_funding_rate: float = DEFAULT_ALERT_FUNDING_THRESHOLD
    alert_score: int = DEFAULT_ALERT_SCORE_THRESHOLD


def determine_signal(item: ScannerItem) -> SignalType:
    """Classify a market snapshot when all required percentage changes exist."""
    oi_change = item.oi_change_pct
    volume_change = item.volume_change_pct
    price_change = item.price_change_pct

    if oi_change is None or price_change is None:
        return SignalType.NEUTRAL
    if oi_change > 0 and volume_change > 0 and price_change > 0:
        return SignalType.LONG_BUILDUP
    if oi_change > 0 and volume_change > 0 and price_change < 0:
        return SignalType.SHORT_BUILDUP
    if oi_change < 0 and price_change < 0:
        return SignalType.LONG_UNWINDING
    if oi_change < 0 and price_change > 0:
        return SignalType.SHORT_COVERING
    return SignalType.NEUTRAL


def calculate_score(item: ScannerItem, thresholds: SignalThresholds) -> int:
    """Return a compact score for future ranking without changing the current UI."""
    score = 0

    if item.oi_change_pct is not None and abs(item.oi_change_pct) >= 0.25:
        score += 3
    if item.volume_change_pct is not None and abs(item.volume_change_pct) >= 0.40:
        score += 3
    if (
        item.oi_change_pct is not None
        and item.oi_change_pct > 0
        and item.price_change_pct is not None
        and abs(item.price_change_pct) <= 0.01
    ):
        score += 4
    if (
        item.funding_change is not None
        and abs(item.funding_change) >= thresholds.alert_funding_rate
    ):
        score += 2

    return score


def apply_filters(
    items: list[ScannerItem],
    filters: ScannerFilters | None,
) -> list[ScannerItem]:
    """Return only items that satisfy all selected scanner filters."""
    if filters is None:
        return items

    filtered: list[ScannerItem] = []
    for item in items:
        selected_exchanges = filters.exchanges
        if selected_exchanges is None and filters.exchange is not None:
            selected_exchanges = frozenset((filters.exchange,))
        if selected_exchanges is not None and item.exchange not in selected_exchanges:
            continue
        if (
            filters.instrument_types is not None
            and InstrumentType(item.instrument_type.removeprefix("USDT "))
            not in filters.instrument_types
        ):
            continue
        if (
            filters.symbol_query
            and filters.symbol_query.upper() not in item.symbol.upper()
        ):
            continue
        if (
            filters.min_oi_change is not None
            and (item.oi_change_pct is None or item.oi_change_pct < filters.min_oi_change)
        ):
            continue
        if (
            filters.max_oi_change is not None
            and (item.oi_change_pct is None or item.oi_change_pct > filters.max_oi_change)
        ):
            continue
        if (
            filters.min_volume_change is not None
            and (
                item.volume_change_pct is None
                or item.volume_change_pct < filters.min_volume_change
            )
        ):
            continue
        if filters.signal is not None and item.signal != filters.signal:
            continue
        filtered.append(item)

    return filtered
