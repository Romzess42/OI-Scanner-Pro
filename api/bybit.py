"""Public Bybit V5 API client used by the scanner."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from api.exchange_client import ExchangeClient
from scanner.models import LiquidationEvent


class BybitAPIError(RuntimeError):
    """Raised when Bybit cannot provide valid market data."""


class BybitClient(ExchangeClient):
    """Fetch publicly available market data for USDT perpetual contracts."""

    BASE_URL = "https://api.bybit.com"
    REQUEST_TIMEOUT_SECONDS = 15
    MAX_KLINE_WORKERS = 8
    exchange_name = "Bybit"
    WEBSOCKET_URL = "wss://stream.bybit.com/v5/public/linear"

    @staticmethod
    def ticker_subscription(symbols: Iterable[str]) -> dict[str, object]:
        return {"op": "subscribe", "args": [f"tickers.{symbol}" for symbol in symbols]}

    @staticmethod
    def liquidation_topics(symbols: Iterable[str]) -> list[str]:
        """Return public all-liquidation topics for the requested contracts."""
        return [f"allLiquidation.{symbol}" for symbol in dict.fromkeys(symbols)]

    @staticmethod
    def parse_ticker_message(message: Mapping[str, Any]) -> dict[str, Any] | None:
        data = message.get("data")
        if not isinstance(data, dict) or not data.get("symbol"):
            return None
        return {"symbol": data["symbol"], "lastPrice": data.get("lastPrice"), "turnover24h": data.get("turnover24h"), "openInterest": data.get("openInterest"), "fundingRate": data.get("fundingRate"), "price24hPcnt": data.get("price24hPcnt")}

    @staticmethod
    def parse_liquidation_message(message: Mapping[str, Any]) -> list[LiquidationEvent]:
        """Normalize Bybit's public ``allLiquidation`` snapshot payload.

        Invalid records are discarded deliberately: the application must never
        invent liquidation data if an exchange sends an incomplete message.
        """
        topic = message.get("topic")
        data = message.get("data")
        if not isinstance(topic, str) or not topic.startswith("allLiquidation."):
            return []
        if not isinstance(data, list):
            return []

        events: list[LiquidationEvent] = []
        for record in data:
            if not isinstance(record, Mapping):
                continue
            try:
                symbol = str(record["s"])
                timestamp_ms = int(record["T"])
                side = str(record["S"])
                quantity = float(record["v"])
                price = float(record["p"])
            except (KeyError, TypeError, ValueError):
                continue
            if not symbol or side not in {"Buy", "Sell"} or quantity < 0 or price < 0:
                continue
            events.append(
                LiquidationEvent(
                    exchange="Bybit",
                    symbol=symbol,
                    timestamp_ms=timestamp_ms,
                    side=side,
                    quantity=quantity,
                    price=price,
                )
            )
        return events

    TIMEFRAME_INTERVALS = {
        "15m": "15",
        "1H": "60",
        "4H": "240",
        "1D": "D",
        "1W": "W",
        "1M": "M",
    }

    def fetch_usdt_perpetual_tickers(self) -> list[dict[str, Any]]:
        """Return ticker records only for currently trading USDT perpetuals."""
        symbols = self._fetch_usdt_perpetual_symbols()
        if not symbols:
            return []

        response = self._get(
            "/v5/market/tickers",
            {"category": "linear"},
        )
        result = response.get("result", {})
        tickers = result.get("list", [])

        if not isinstance(tickers, list):
            raise BybitAPIError("Bybit returned an invalid ticker list.")

        return [
            ticker
            for ticker in tickers
            if isinstance(ticker, dict) and ticker.get("symbol") in symbols
        ]

    def fetch_previous_close_prices(
        self,
        symbols: Iterable[str],
        timeframe: str,
    ) -> dict[str, float]:
        """Return the previous completed candle close for each requested symbol.

        Bybit's Kline API accepts one symbol per request.  The scanner therefore
        limits this method to its most liquid instruments and uses a deliberately
        small worker pool.
        """
        try:
            interval = self.TIMEFRAME_INTERVALS[timeframe]
        except KeyError as error:
            raise ValueError(f"Unsupported Bybit timeframe: {timeframe}") from error

        unique_symbols = list(dict.fromkeys(symbols))
        close_prices: dict[str, float] = {}

        with ThreadPoolExecutor(max_workers=self.MAX_KLINE_WORKERS) as executor:
            futures = {
                executor.submit(self._fetch_previous_close, symbol, interval): symbol
                for symbol in unique_symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    close_price = future.result()
                except BybitAPIError:
                    continue

                if close_price is not None:
                    close_prices[symbol] = close_price

        return close_prices

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[dict[str, float]]:
        """Return chronological completed OHLC candles for Instrument Analysis."""
        try:
            interval = self.TIMEFRAME_INTERVALS[timeframe]
        except KeyError as error:
            raise ValueError(f"Unsupported Bybit timeframe: {timeframe}") from error
        response = self._get(
            "/v5/market/kline",
            {"category": "linear", "symbol": symbol, "interval": interval, "limit": limit},
        )
        result: list[dict[str, float]] = []
        for candle in reversed(response.get("result", {}).get("list", [])):
            if not isinstance(candle, list) or len(candle) < 5:
                continue
            try:
                result.append({"timestamp_ms": float(candle[0]), "open": float(candle[1]), "high": float(candle[2]), "low": float(candle[3]), "close": float(candle[4])})
            except (TypeError, ValueError):
                continue
        return result

    def _fetch_usdt_perpetual_symbols(self) -> set[str]:
        symbols: set[str] = set()
        cursor: str | None = None

        while True:
            params: dict[str, str | int] = {
                "category": "linear",
                "limit": 1_000,
            }
            if cursor:
                params["cursor"] = cursor

            response = self._get("/v5/market/instruments-info", params)
            result = response.get("result", {})
            instruments = result.get("list", [])

            if not isinstance(instruments, list):
                raise BybitAPIError("Bybit returned an invalid instruments list.")

            symbols.update(
                instrument["symbol"]
                for instrument in instruments
                if isinstance(instrument, dict)
                and self.is_usdt_perpetual(instrument)
                and isinstance(instrument.get("symbol"), str)
            )

            next_cursor = result.get("nextPageCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor

        return symbols

    @staticmethod
    def is_usdt_perpetual(instrument: Mapping[str, Any]) -> bool:
        """Return whether a Bybit instrument is a tradable USDT perpetual."""
        return (
            instrument.get("contractType") == "LinearPerpetual"
            and instrument.get("settleCoin") == "USDT"
            and instrument.get("status") == "Trading"
        )

    def _fetch_previous_close(self, symbol: str, interval: str) -> float | None:
        response = self._get(
            "/v5/market/kline",
            {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": 2,
            },
        )
        candles = response.get("result", {}).get("list", [])

        if not isinstance(candles, list) or len(candles) < 2:
            return None

        # Bybit returns candles in reverse chronological order.  With a limit
        # of two, the second record is the previous completed interval.
        previous_candle = candles[1]
        if not isinstance(previous_candle, list) or len(previous_candle) < 5:
            return None

        try:
            return float(previous_candle[4])
        except (TypeError, ValueError):
            return None

    def _get(
        self,
        path: str,
        params: Mapping[str, str | int],
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}{path}?{urlencode(params)}"

        try:
            with urlopen(url, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise BybitAPIError(f"Unable to load Bybit market data: {error}") from error

        if not isinstance(payload, dict):
            raise BybitAPIError("Bybit returned an invalid response.")

        if payload.get("retCode") != 0:
            message = payload.get("retMsg", "Unknown Bybit API error")
            raise BybitAPIError(f"Bybit API error: {message}")

        return payload
