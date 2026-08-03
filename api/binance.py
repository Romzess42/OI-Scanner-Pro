"""Public Binance USD-M Futures adapter."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from api.exchange_client import ExchangeClient
from scanner.models import LiquidationEvent


class BinanceAPIError(RuntimeError):
    """Raised when Binance Futures public market data cannot be loaded."""


class BinanceClient(ExchangeClient):
    """Normalize Binance USD-M perpetual public data for the scanner."""

    BASE_URL = "https://fapi.binance.com"
    SPOT_BASE_URL = "https://api.binance.com"
    REQUEST_TIMEOUT_SECONDS = 15
    MAX_DETAILS_WORKERS = 8
    exchange_name = "Binance"
    WEBSOCKET_URL = "wss://fstream.binance.com/stream?streams="

    @staticmethod
    def ticker_stream_url(symbols: Iterable[str]) -> str:
        return BinanceClient.WEBSOCKET_URL + "/".join(f"{symbol.lower()}@ticker" for symbol in symbols)

    @staticmethod
    def market_stream_url(symbols: Iterable[str]) -> str:
        """Return tickers, best quotes and public force orders in one stream."""
        streams: list[str] = []
        for symbol in dict.fromkeys(symbols):
            streams.extend(
                (
                    f"{symbol.lower()}@ticker",
                    f"{symbol.lower()}@bookTicker",
                    f"{symbol.lower()}@forceOrder",
                )
            )
        return BinanceClient.WEBSOCKET_URL + "/".join(streams)

    @staticmethod
    def parse_ticker_message(message: dict[str, Any]) -> dict[str, Any] | None:
        data = message.get("data", message)
        if not isinstance(data, dict) or not data.get("s"):
            return None
        if data.get("c") is not None:
            return {
                "symbol": data["s"], "lastPrice": data.get("c"),
                "turnover24h": data.get("q"), "openInterest": None,
                "fundingRate": None,
                "price24hPcnt": BinanceClient._percent_decimal(data.get("P")),
            }
        # A best bid/ask update is a safe price fallback when the 24-hour ticker
        # stream is delayed by a network or regional gateway.
        if data.get("a") is not None or data.get("b") is not None:
            return {
                "symbol": data["s"],
                "lastPrice": data.get("a") or data.get("b"),
                "turnover24h": None, "openInterest": None,
                "fundingRate": None, "price24hPcnt": None,
            }
        return None

    @staticmethod
    def parse_liquidation_message(message: dict[str, Any]) -> list[LiquidationEvent]:
        """Normalize a public USD-M Futures ``forceOrder`` event.

        Binance's combined stream wraps the event in ``data``; direct streams do
        not.  The raw order side is retained for exchange-specific chart labels.
        """
        data = message.get("data", message)
        if not isinstance(data, dict) or data.get("e") != "forceOrder":
            return []
        order = data.get("o")
        if not isinstance(order, dict):
            return []
        try:
            symbol = str(order["s"])
            timestamp_ms = int(order.get("T", data["E"]))
            side = str(order["S"])
            quantity = float(order["q"])
            price = float(order.get("ap") or order["p"])
        except (KeyError, TypeError, ValueError):
            return []
        if not symbol or side not in {"BUY", "SELL"} or quantity < 0 or price < 0:
            return []
        return [
            LiquidationEvent(
                exchange="Binance",
                symbol=symbol,
                timestamp_ms=timestamp_ms,
                side=side,
                quantity=quantity,
                price=price,
            )
        ]
    TIMEFRAME_INTERVALS = {
        "15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w", "1M": "1M"
    }

    def fetch_usdt_perpetual_tickers(self) -> list[dict[str, Any]]:
        instruments = self._get("/fapi/v1/exchangeInfo")
        symbols = {
            entry["symbol"]
            for entry in instruments.get("symbols", [])
            if isinstance(entry, dict)
            and entry.get("contractType") == "PERPETUAL"
            and entry.get("quoteAsset") == "USDT"
            and entry.get("status") == "TRADING"
        }
        tickers = self._get("/fapi/v1/ticker/24hr")
        if not isinstance(tickers, list):
            raise BinanceAPIError("Binance returned an invalid ticker list.")
        selected = [ticker for ticker in tickers if ticker.get("symbol") in symbols]
        selected.sort(key=lambda ticker: self._float(ticker.get("quoteVolume")) or 0, reverse=True)
        details = self._fetch_details([ticker["symbol"] for ticker in selected[:100]])
        return [
            {
                "symbol": ticker["symbol"],
                "lastPrice": ticker.get("lastPrice"),
                "turnover24h": ticker.get("quoteVolume"),
                "openInterest": details.get(ticker["symbol"], {}).get("openInterest"),
                "price24hPcnt": self._percent_decimal(ticker.get("priceChangePercent")),
                "fundingRate": details.get(ticker["symbol"], {}).get("fundingRate"),
            }
            for ticker in selected
        ]

    def fetch_market_tickers(self, instrument_types: Iterable[str]) -> list[dict[str, Any]]:
        """Return Binance USDT Spot, perpetual and delivery-futures tickers."""
        requested = set(instrument_types)
        records: list[dict[str, Any]] = []
        if "Perpetual" in requested:
            records.extend(
                {**ticker, "instrumentType": "Perpetual"}
                for ticker in self.fetch_usdt_perpetual_tickers()
            )
        if "Spot" in requested:
            records.extend(self._fetch_spot_tickers())
        if "Futures" in requested:
            records.extend(self._fetch_delivery_futures_tickers())
        return records

    def fetch_previous_close_prices(self, symbols: Iterable[str], timeframe: str) -> dict[str, float]:
        interval = self.TIMEFRAME_INTERVALS[timeframe]
        result: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {executor.submit(self._previous_close, symbol, interval): symbol for symbol in dict.fromkeys(symbols)}
            for future in as_completed(futures):
                try:
                    value = future.result()
                except BinanceAPIError:
                    continue
                if value is not None:
                    result[futures[future]] = value
        return result

    def fetch_previous_close_prices_for_type(
        self, symbols: Iterable[str], timeframe: str, instrument_type: str
    ) -> dict[str, float]:
        interval = self.TIMEFRAME_INTERVALS[timeframe]
        loader = self._spot_previous_close if instrument_type == "Spot" else self._previous_close
        result: dict[str, float] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {
                executor.submit(loader, symbol, interval): symbol
                for symbol in dict.fromkeys(symbols)
            }
            for future in as_completed(futures):
                try:
                    value = future.result()
                except BinanceAPIError:
                    continue
                if value is not None:
                    result[futures[future]] = value
        return result

    def fetch_ohlc(
        self, symbol: str, timeframe: str, limit: int = 200
    ) -> list[dict[str, float]]:
        """Return chronological USD-M Futures candles for Instrument Analysis."""
        try:
            interval = self.TIMEFRAME_INTERVALS[timeframe]
        except KeyError as error:
            raise ValueError(f"Unsupported Binance timeframe: {timeframe}") from error
        candles = self._get(
            "/fapi/v1/klines",
            {"symbol": symbol, "interval": interval, "limit": limit},
        )
        if not isinstance(candles, list):
            raise BinanceAPIError("Binance returned an invalid candle list.")
        result: list[dict[str, float]] = []
        for candle in candles:
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

    def _fetch_details(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        details: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.MAX_DETAILS_WORKERS) as executor:
            futures = {executor.submit(self._fetch_detail, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                try:
                    details[futures[future]] = future.result()
                except BinanceAPIError:
                    details[futures[future]] = {}
        return details

    def _fetch_detail(self, symbol: str) -> dict[str, Any]:
        try:
            oi = self._get("/fapi/v1/openInterest", {"symbol": symbol})
        except BinanceAPIError:
            oi = {}
        try:
            funding = self._get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})
        except BinanceAPIError:
            funding = []
        latest = funding[-1] if isinstance(funding, list) and funding else {}
        return {"openInterest": oi.get("openInterest"), "fundingRate": latest.get("fundingRate")}

    def _previous_close(self, symbol: str, interval: str) -> float | None:
        candles = self._get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": 2})
        if not isinstance(candles, list) or len(candles) < 2:
            return None
        return self._float(candles[-2][4])

    def _spot_previous_close(self, symbol: str, interval: str) -> float | None:
        candles = self._spot_get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": 2})
        if not isinstance(candles, list) or len(candles) < 2:
            return None
        return self._float(candles[-2][4])

    def _fetch_spot_tickers(self) -> list[dict[str, Any]]:
        instruments = self._spot_get("/api/v3/exchangeInfo")
        symbols = {
            item["symbol"]
            for item in instruments.get("symbols", [])
            if isinstance(item, dict)
            and item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
        }
        tickers = self._spot_get("/api/v3/ticker/24hr")
        return [
            {
                "symbol": ticker["symbol"], "lastPrice": ticker.get("lastPrice"),
                "turnover24h": ticker.get("quoteVolume"), "openInterest": None,
                "price24hPcnt": self._percent_decimal(ticker.get("priceChangePercent")),
                "fundingRate": None, "instrumentType": "Spot",
            }
            for ticker in tickers
            if isinstance(ticker, dict) and ticker.get("symbol") in symbols
        ]

    def _fetch_delivery_futures_tickers(self) -> list[dict[str, Any]]:
        instruments = self._get("/fapi/v1/exchangeInfo")
        symbols = {
            item["symbol"]
            for item in instruments.get("symbols", [])
            if isinstance(item, dict)
            and item.get("contractType") in {"CURRENT_QUARTER", "NEXT_QUARTER"}
            and item.get("quoteAsset") == "USDT"
            and item.get("status") == "TRADING"
        }
        tickers = self._get("/fapi/v1/ticker/24hr")
        selected = [ticker for ticker in tickers if ticker.get("symbol") in symbols]
        details = self._fetch_details([ticker["symbol"] for ticker in selected[:100]])
        return [
            {
                "symbol": ticker["symbol"], "lastPrice": ticker.get("lastPrice"),
                "turnover24h": ticker.get("quoteVolume"),
                "openInterest": details.get(ticker["symbol"], {}).get("openInterest"),
                "price24hPcnt": self._percent_decimal(ticker.get("priceChangePercent")),
                "fundingRate": None, "instrumentType": "Futures",
            }
            for ticker in selected
        ]

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(params)}" if params else ""
        try:
            with urlopen(f"{self.BASE_URL}{path}{suffix}", timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise BinanceAPIError(f"Unable to load Binance market data: {error}") from error

    def _spot_get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        suffix = f"?{urlencode(params)}" if params else ""
        try:
            with urlopen(f"{self.SPOT_BASE_URL}{path}{suffix}", timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise BinanceAPIError(f"Unable to load Binance Spot market data: {error}") from error

    @staticmethod
    def _float(value: object) -> float | None:
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _percent_decimal(cls, value: object) -> float | None:
        number = cls._float(value)
        return number / 100 if number is not None else None
