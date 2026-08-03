"""Public OKX USDT swap adapter."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from api.exchange_client import ExchangeClient


class OKXAPIError(RuntimeError):
    """Raised when OKX public market data cannot be loaded."""


class OKXClient(ExchangeClient):
    """Normalize OKX USDT-margined swap public data for the scanner."""

    BASE_URL = "https://www.okx.com"
    REQUEST_TIMEOUT_SECONDS = 15
    MAX_DETAILS_WORKERS = 8
    exchange_name = "OKX"
    WEBSOCKET_URL = "wss://ws.okx.com:8443/ws/v5/public"

    @staticmethod
    def ticker_subscription(symbols: Iterable[str]) -> dict[str, object]:
        return {"op": "subscribe", "args": [{"channel": "tickers", "instId": symbol} for symbol in symbols]}
    TIMEFRAME_BARS = {"15m": "15m", "1H": "1H", "4H": "4H", "1D": "1D", "1W": "1W", "1M": "1M"}

    def fetch_usdt_perpetual_tickers(self) -> list[dict[str, Any]]:
        instruments = self._get("/api/v5/public/instruments", {"instType": "SWAP"})
        symbols = {
            entry["instId"]
            for entry in instruments
            if entry.get("settleCcy") == "USDT" and entry.get("state") == "live"
        }
        tickers = [ticker for ticker in self._get("/api/v5/market/tickers", {"instType": "SWAP"}) if ticker.get("instId") in symbols]
        tickers.sort(key=lambda ticker: self._float(ticker.get("volCcy24h")) or 0, reverse=True)
        details = self._fetch_details([ticker["instId"] for ticker in tickers[:100]])
        return [
            {
                "symbol": ticker["instId"], "lastPrice": ticker.get("last"),
                "turnover24h": ticker.get("volCcy24h"),
                "openInterest": details.get(ticker["instId"], {}).get("openInterest"),
                "price24hPcnt": self._change(ticker.get("last"), ticker.get("open24h")),
                "fundingRate": details.get(ticker["instId"], {}).get("fundingRate"),
            }
            for ticker in tickers
        ]

    def fetch_market_tickers(self, instrument_types: Iterable[str]) -> list[dict[str, Any]]:
        """Return OKX USDT Spot, swaps and dated futures using public endpoints."""
        requested = set(instrument_types)
        records: list[dict[str, Any]] = []
        if "Perpetual" in requested:
            records.extend(
                {**ticker, "instrumentType": "Perpetual"}
                for ticker in self.fetch_usdt_perpetual_tickers()
            )
        if "Spot" in requested:
            records.extend(self._fetch_tickers_for_type("SPOT", "Spot"))
        if "Futures" in requested:
            records.extend(self._fetch_tickers_for_type("FUTURES", "Futures"))
        return records

    def fetch_previous_close_prices(self, symbols: Iterable[str], timeframe: str) -> dict[str, float]:
        bar = self.TIMEFRAME_BARS[timeframe]
        result: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {executor.submit(self._previous_close, symbol, bar): symbol for symbol in dict.fromkeys(symbols)}
            for future in as_completed(futures):
                try:
                    value = future.result()
                except OKXAPIError:
                    continue
                if value is not None:
                    result[futures[future]] = value
        return result

    def fetch_previous_close_prices_for_type(
        self, symbols: Iterable[str], timeframe: str, instrument_type: str
    ) -> dict[str, float]:
        bar = self.TIMEFRAME_BARS[timeframe]
        result: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {
                executor.submit(self._previous_close, symbol, bar): symbol
                for symbol in dict.fromkeys(symbols)
            }
            for future in as_completed(futures):
                try:
                    value = future.result()
                except OKXAPIError:
                    continue
                if value is not None:
                    result[futures[future]] = value
        return result

    def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> list[dict[str, float]]:
        """Return chronological public swap candles for Instrument Analysis."""
        try:
            bar = self.TIMEFRAME_BARS[timeframe]
        except KeyError as error:
            raise ValueError(f"Unsupported OKX timeframe: {timeframe}") from error
        candles = self._get(
            "/api/v5/market/candles",
            {"instId": symbol, "bar": bar, "limit": limit},
        )
        result: list[dict[str, float]] = []
        # OKX returns newest candle first.
        for candle in reversed(candles):
            if not isinstance(candle, list) or len(candle) < 5:
                continue
            try:
                result.append(
                    {
                        "timestamp_ms": float(candle[0]),
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                    }
                )
            except (TypeError, ValueError):
                continue
        return result

    def _fetch_details(self, symbols: list[str], inst_type: str = "SWAP") -> dict[str, dict[str, Any]]:
        details: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {executor.submit(self._fetch_detail, symbol, inst_type): symbol for symbol in symbols}
            for future in as_completed(futures):
                try:
                    details[futures[future]] = future.result()
                except OKXAPIError:
                    details[futures[future]] = {}
        return details

    def _fetch_detail(self, symbol: str, inst_type: str = "SWAP") -> dict[str, Any]:
        oi = self._get("/api/v5/public/open-interest", {"instType": inst_type, "instId": symbol})
        funding = self._get("/api/v5/public/funding-rate", {"instId": symbol}) if inst_type == "SWAP" else []
        return {"openInterest": (oi[0].get("oiUsd") if oi else None), "fundingRate": (funding[0].get("fundingRate") if funding else None)}

    def _previous_close(self, symbol: str, bar: str) -> float | None:
        candles = self._get("/api/v5/market/candles", {"instId": symbol, "bar": bar, "limit": 2})
        return self._float(candles[1][4]) if len(candles) >= 2 else None

    def _fetch_tickers_for_type(self, inst_type: str, instrument_type: str) -> list[dict[str, Any]]:
        instruments = self._get("/api/v5/public/instruments", {"instType": inst_type})
        if inst_type == "SPOT":
            symbols = {
                item["instId"]
                for item in instruments
                if item.get("quoteCcy") == "USDT" and item.get("state") == "live"
            }
        else:
            symbols = {
                item["instId"]
                for item in instruments
                # OKX currently lists dated futures settled in BTC, ETH or USD;
                # excluding non-USDT settlement would make its Futures menu empty.
                if item.get("state") == "live"
            }
        tickers = [
            ticker for ticker in self._get("/api/v5/market/tickers", {"instType": inst_type})
            if ticker.get("instId") in symbols
        ]
        open_interest = self._fetch_bulk_open_interest(inst_type) if inst_type == "FUTURES" else {}
        return [
            {
                "symbol": ticker["instId"], "lastPrice": ticker.get("last"),
                "turnover24h": ticker.get("volCcy24h"),
                "openInterest": open_interest.get(ticker["instId"]),
                "price24hPcnt": self._change(ticker.get("last"), ticker.get("open24h")),
                "fundingRate": None, "instrumentType": instrument_type,
                "instrumentLabel": "Futures" if inst_type == "FUTURES" else None,
            }
            for ticker in tickers
        ]

    def _fetch_bulk_open_interest(self, inst_type: str) -> dict[str, object]:
        """Use one OKX public request instead of one OI request per future."""
        rows = self._get("/api/v5/public/open-interest", {"instType": inst_type})
        return {
            str(row["instId"]): row.get("oiUsd") or row.get("oi")
            for row in rows
            if isinstance(row, dict) and row.get("instId")
        }

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            request = Request(
                f"{self.BASE_URL}{path}?{urlencode(params)}",
                headers={"User-Agent": "OI-Scanner-Pro/1.0"},
            )
            with urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise OKXAPIError(f"Unable to load OKX market data: {error}") from error
        if not isinstance(payload, dict) or payload.get("code") != "0":
            raise OKXAPIError(f"OKX API error: {payload.get('msg', 'invalid response') if isinstance(payload, dict) else 'invalid response'}")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    @staticmethod
    def _float(value: object) -> float | None:
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _change(cls, current: object, opening: object) -> float | None:
        current_value, opening_value = cls._float(current), cls._float(opening)
        return (current_value - opening_value) / opening_value if current_value is not None and opening_value not in (None, 0) else None
