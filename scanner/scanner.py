"""Services that transform exchange data into scanner items."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from api.bybit import BybitClient
from api.exchange_manager import ExchangeManager
from config import DATABASE_NAME
from database.database import HistoryRepository, HistorySnapshot
from scanner.filters import (
    ScannerFilters,
    SignalThresholds,
    apply_filters,
    calculate_score,
    determine_signal,
)
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


class HistoryDataProvider(Protocol):
    """The part of the history repository required by ScannerService."""

    def get_baselines(
        self,
        exchange: str,
        symbols: list[str],
        before: datetime,
    ) -> dict[str, HistorySnapshot]:
        """Return historical snapshots at or before the requested time."""

    def save_snapshots(self, items: list[ScannerItem]) -> None:
        """Persist the current scanner snapshots."""

    def count_snapshots(self) -> int:
        """Return the total number of local history records."""


@dataclass(frozen=True, slots=True)
class HistoryStatus:
    """Summary of historical baselines available for one scanner refresh."""

    timeframe: str
    available_items: int
    total_items: int
    saved_items: int
    total_snapshots: int

    @property
    def message(self) -> str:
        if not self.total_items or not self.available_items:
            progress = f"History: {self.timeframe} collecting"
        elif self.available_items == self.total_items:
            progress = f"History: {self.timeframe} ready"
        else:
            progress = (
                f"History: {self.timeframe} "
                f"{self.available_items}/{self.total_items} ready"
            )
        return (
            f"{progress} | Saved: {self.saved_items} | "
            f"Total: {self.total_snapshots}"
        )


class ScannerService:
    """Load and normalize market data for the scanner interface."""

    PRICE_CHANGE_SYMBOL_LIMIT = 100
    TIMEFRAME_DELTAS = {
        "15m": timedelta(minutes=15),
        "1H": timedelta(hours=1),
        "4H": timedelta(hours=4),
        "1D": timedelta(days=1),
        "1W": timedelta(days=7),
        "1M": timedelta(days=30),
    }

    def __init__(
        self,
        bybit_client: BybitDataProvider | None = None,
        history_repository: HistoryDataProvider | None = None,
        exchange_manager: ExchangeManager | None = None,
    ):
        self._bybit_client = bybit_client
        self._exchange_manager = (
            exchange_manager if bybit_client is None else None
        )
        if self._bybit_client is None and self._exchange_manager is None:
            self._exchange_manager = ExchangeManager()
        self._history_repository = history_repository or HistoryRepository(
            DATABASE_NAME
        )
        self.last_history_status = HistoryStatus("15m", 0, 0, 0, 0)
        self.last_refreshed_items: list[ScannerItem] = []

    def refresh(
        self,
        timeframe: str = "15m",
        filters: ScannerFilters | None = None,
        thresholds: SignalThresholds | None = None,
    ) -> list[ScannerItem]:
        """Load data and calculate price change for the 100 most-liquid symbols."""
        thresholds = thresholds or SignalThresholds()
        updated_at = datetime.now(timezone.utc)
        clients = self._get_clients(filters)
        clients_by_exchange = {
            getattr(client, "exchange_name", "Bybit"): client
            for client in clients
        }
        items: list[ScannerItem] = []
        for exchange, client in clients_by_exchange.items():
            try:
                tickers = client.fetch_usdt_perpetual_tickers()
            except RuntimeError:
                continue
            items.extend(
                self._build_item(ticker, updated_at, exchange)
                for ticker in tickers
                if isinstance(ticker, dict) and ticker.get("symbol")
            )
        sorted_items = sorted(
            items,
            key=lambda item: item.volume_24h or 0.0,
            reverse=True,
        )
        baselines: dict[tuple[str, str], HistorySnapshot] = {}
        previous_closes: dict[tuple[str, str], float] = {}
        for exchange, client in clients_by_exchange.items():
            exchange_items = [item for item in sorted_items if item.exchange == exchange]
            exchange_baselines = self._history_repository.get_baselines(
                exchange,
                [item.symbol for item in exchange_items],
                updated_at - self._get_timeframe_delta(timeframe),
            )
            baselines.update(
                {(exchange, symbol): snapshot for symbol, snapshot in exchange_baselines.items()}
            )
            try:
                prices = client.fetch_previous_close_prices(
                    [item.symbol for item in exchange_items[: self.PRICE_CHANGE_SYMBOL_LIMIT]],
                    timeframe,
                )
            except RuntimeError:
                prices = {}
            previous_closes.update(
                {(exchange, symbol): price for symbol, price in prices.items()}
            )

        enriched_items: list[ScannerItem] = []
        for item in sorted_items:
            baseline = baselines.get((item.exchange, item.symbol))
            previous_price = previous_closes.get((item.exchange, item.symbol))
            if previous_price is None and baseline is not None:
                previous_price = baseline.price

            changed_item = replace(
                item,
                price_change_pct=self._calculate_price_change(
                    item.price,
                    previous_price,
                ),
                oi_change_pct=self._calculate_change(
                    item.open_interest,
                    baseline.open_interest if baseline else None,
                ),
                volume_change_pct=self._calculate_change(
                    item.volume_24h,
                    baseline.volume_24h if baseline else None,
                ),
                funding_change=self._calculate_difference(
                    item.funding_rate,
                    baseline.funding_rate if baseline else None,
                ),
            )
            enriched_items.append(
                replace(
                    changed_item,
                    signal=determine_signal(changed_item),
                    score=calculate_score(changed_item, thresholds),
                )
            )
        self._history_repository.save_snapshots(enriched_items)
        self.last_history_status = HistoryStatus(
            timeframe,
            len(baselines),
            len(sorted_items),
            len(enriched_items),
            self._history_repository.count_snapshots(),
        )
        self.last_refreshed_items = enriched_items
        return apply_filters(enriched_items, filters)

    @staticmethod
    def _build_item(
        ticker: dict[str, Any], updated_at: datetime, exchange: str = "Bybit"
    ) -> ScannerItem:
        return ScannerItem(
            symbol=str(ticker["symbol"]),
            exchange=exchange,
            instrument_type="USDT Perpetual",
            price=ScannerService._as_float(ticker.get("lastPrice")),
            volume_24h=ScannerService._as_float(ticker.get("turnover24h")),
            open_interest=ScannerService._as_float(ticker.get("openInterest")),
            oi_change_pct=None,
            volume_change_pct=None,
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

    @staticmethod
    def _calculate_change(
        current_value: float | None,
        previous_value: float | None,
    ) -> float | None:
        if current_value is None or previous_value in (None, 0):
            return None
        return (current_value - previous_value) / previous_value

    @staticmethod
    def _calculate_difference(
        current_value: float | None,
        previous_value: float | None,
    ) -> float | None:
        if current_value is None or previous_value is None:
            return None
        return current_value - previous_value

    @classmethod
    def _get_timeframe_delta(cls, timeframe: str) -> timedelta:
        try:
            return cls.TIMEFRAME_DELTAS[timeframe]
        except KeyError as error:
            raise ValueError(f"Unsupported history timeframe: {timeframe}") from error

    def _get_clients(self, filters: ScannerFilters | None) -> list[BybitDataProvider]:
        """Select active exchange adapters while preserving the v0.5 injection API."""
        if self._exchange_manager is not None:
            return self._exchange_manager.get_clients(
                filters.exchange if filters is not None else None
            )
        return [self._bybit_client] if self._bybit_client is not None else [BybitClient()]

    def apply_live_update(self, exchange: str, update: dict[str, Any]) -> ScannerItem | None:
        """Merge one normalized ticker update without another REST refresh."""
        symbol = update.get("symbol")
        if not isinstance(symbol, str):
            return None
        for index, item in enumerate(self.last_refreshed_items):
            if item.exchange == exchange and item.symbol == symbol:
                changed = replace(
                    item,
                    price=self._as_float(update.get("lastPrice")) or item.price,
                    volume_24h=self._as_float(update.get("turnover24h")) or item.volume_24h,
                    open_interest=self._as_float(update.get("openInterest")) or item.open_interest,
                    funding_rate=self._as_float(update.get("fundingRate")) or item.funding_rate,
                    updated_at=datetime.now(timezone.utc),
                )
                self.last_refreshed_items[index] = changed
                return changed
        return None
