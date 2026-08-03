"""Domain models used by the market scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SignalType(str, Enum):
    """Market-position signals derived from OI, volume and price changes."""

    NONE = ""
    LONG_BUILDUP = "Long Buildup"
    SHORT_BUILDUP = "Short Buildup"
    LONG_UNWINDING = "Long Unwinding"
    SHORT_COVERING = "Short Covering"
    NEUTRAL = "Neutral"

    # Compatibility aliases retained for code written before v0.6.
    LONG_EXIT = LONG_UNWINDING
    SHORT_EXIT = SHORT_COVERING


@dataclass(frozen=True, slots=True)
class ScannerItem:
    """A normalized market snapshot shown in the scanner table."""

    symbol: str
    exchange: str
    instrument_type: str
    price: float | None
    volume_24h: float | None
    open_interest: float | None
    oi_change_pct: float | None
    volume_change_pct: float | None
    price_change_pct_24h: float | None
    price_change_pct: float | None
    funding_rate: float | None
    updated_at: datetime
    funding_change: float | None = None
    signal: SignalType = SignalType.NONE
    score: int = 0


@dataclass(frozen=True, slots=True)
class LiquidationEvent:
    """One public liquidation reported by an exchange market-data stream.

    ``side`` retains the exchange position side.  On Bybit, ``Buy`` denotes a
    liquidated long position and ``Sell`` denotes a liquidated short position.
    """

    exchange: str
    symbol: str
    timestamp_ms: int
    side: str
    quantity: float
    price: float
