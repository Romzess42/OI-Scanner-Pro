"""Public OKX USDT swap adapter."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

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

    def _fetch_details(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        details: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {executor.submit(self._fetch_detail, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                try:
                    details[futures[future]] = future.result()
                except OKXAPIError:
                    details[futures[future]] = {}
        return details

    def _fetch_detail(self, symbol: str) -> dict[str, Any]:
        oi = self._get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": symbol})
        funding = self._get("/api/v5/public/funding-rate", {"instId": symbol})
        return {"openInterest": (oi[0].get("oiUsd") if oi else None), "fundingRate": (funding[0].get("fundingRate") if funding else None)}

    def _previous_close(self, symbol: str, bar: str) -> float | None:
        candles = self._get("/api/v5/market/candles", {"instId": symbol, "bar": bar, "limit": 2})
        return self._float(candles[1][4]) if len(candles) >= 2 else None

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with urlopen(f"{self.BASE_URL}{path}?{urlencode(params)}", timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
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
