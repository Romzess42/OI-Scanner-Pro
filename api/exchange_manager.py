"""Registry and selection logic for supported public exchange clients."""

from __future__ import annotations

from collections.abc import Iterable

from api.binance import BinanceClient
from api.bybit import BybitClient
from api.exchange_client import ExchangeClient
from api.okx import OKXClient


class ExchangeManager:
    """Own only Bybit, Binance Futures and OKX client adapters."""

    def __init__(self, clients: Iterable[ExchangeClient] | None = None):
        active_clients = clients or (BybitClient(), BinanceClient(), OKXClient())
        self._clients = {client.exchange_name: client for client in active_clients}

    def get_clients(self, exchanges: str | Iterable[str] | None = None) -> list[ExchangeClient]:
        if exchanges is None:
            return list(self._clients.values())
        if isinstance(exchanges, str):
            exchanges = (exchanges,)
        return [self._clients[name] for name in exchanges if name in self._clients]

    @property
    def exchanges(self) -> tuple[str, ...]:
        return tuple(self._clients)
