"""Domain models used by the market scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ScannerItem:
    """A normalized market snapshot shown in the scanner table."""

    symbol: str
    exchange: str
    instrument_type: str
    price: float | None
    volume_24h: float | None
    open_interest: float | None
    price_change_pct_24h: float | None
    price_change_pct: float | None
    funding_rate: float | None
    updated_at: datetime
