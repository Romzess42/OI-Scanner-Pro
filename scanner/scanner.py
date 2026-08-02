"""Services that transform exchange data into scanner items."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Protocol

from api.bybit import BybitClient
from scanner.models import ScannerItem


class BybitDataProvider(Protocol):
    """The part of the Bybit client required by ScannerService."""

    def fetch_usdt_perpetual_tickers(self) -> list[dict[str, Any]]:
        """Return raw Bybit ticker records for USDT perpetuals."""

    def fetch_previous_close_prices(
        self,
        symbols: list[str],
        timeframe: str,
    ) -> dict[str, float]:
        """Return the previous completed candle close for each symbol."""


class ScannerService:
    """Load and normalize market data for the scanner interface."""

    PRICE_CHANGE_SYMBOL_LIMIT = 100

    def __init__(self, bybit_client: BybitDataProvider | None = None):
        self._bybit_client = bybit_client or BybitClient()

    def refresh(self, timeframe: str = "15m") -> list[ScannerItem]:
        """Load data and calculate price change for the 100 most-liquid symbols."""
        updated_at = datetime.now(timezone.utc)
        items = [
            self._build_item(ticker, updated_at)
            for ticker in self._bybit_client.fetch_usdt_perpetual_tickers()
            if isinstance(ticker, dict) and ticker.get("symbol")
        ]
        sorted_items = sorted(
            items,
            key=lambda item: item.volume_24h or 0.0,
            reverse=True,
        )
        top_symbols = [
            item.symbol for item in sorted_items[: self.PRICE_CHANGE_SYMBOL_LIMIT]
        ]
        previous_closes = self._bybit_client.fetch_previous_close_prices(
            top_symbols,
            timeframe,
        )

        return [
            replace(
                item,
                price_change_pct=self._calculate_price_change(
                    item.price,
                    previous_closes.get(item.symbol),
                ),
            )
            for item in sorted_items
        ]

    @staticmethod
    def _build_item(ticker: dict[str, Any], updated_at: datetime) -> ScannerItem:
        return ScannerItem(
            symbol=str(ticker["symbol"]),
            exchange="Bybit",
            instrument_type="USDT Perpetual",
            price=ScannerService._as_float(ticker.get("lastPrice")),
            volume_24h=ScannerService._as_float(ticker.get("turnover24h")),
            open_interest=ScannerService._as_float(ticker.get("openInterest")),
            price_change_pct_24h=ScannerService._as_float(
                ticker.get("price24hPcnt")
            ),
            price_change_pct=None,
            funding_rate=ScannerService._as_float(ticker.get("fundingRate")),
            updated_at=updated_at,
        )

    @staticmethod
    def _as_float(value: object) -> float | None:
        if value in (None, ""):
            return None

        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _calculate_price_change(
        current_price: float | None,
        previous_close: float | None,
    ) -> float | None:
        if current_price is None or previous_close in (None, 0):
            return None
        return (current_price - previous_close) / previous_close
