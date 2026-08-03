"""Common public-market interface implemented by every supported exchange."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class ExchangeClient(ABC):
    """Return a common raw ticker shape consumable by the scanner service."""

    exchange_name: str

    @abstractmethod
    def fetch_usdt_perpetual_tickers(self) -> list[dict[str, Any]]:
        """Return normalized ticker records for tradable USDT perpetuals."""

    @abstractmethod
    def fetch_previous_close_prices(
        self, symbols: Iterable[str], timeframe: str
    ) -> dict[str, float]:
        """Return previous completed closes keyed by the exchange symbol."""

    def fetch_market_tickers(self, instrument_types: Iterable[str]) -> list[dict[str, Any]]:
        """Return market-type tagged records; subclasses add Spot/Futures support."""
        return (
            [
                {**ticker, "instrumentType": "Perpetual"}
                for ticker in self.fetch_usdt_perpetual_tickers()
            ]
            if "Perpetual" in instrument_types
            else []
        )

    def fetch_previous_close_prices_for_type(
        self, symbols: Iterable[str], timeframe: str, instrument_type: str
    ) -> dict[str, float]:
        """Return prior closes for one market type, preserving legacy adapters."""
        return self.fetch_previous_close_prices(symbols, timeframe)
