"""Background WebSocket connections with reconnect and status callbacks."""
from __future__ import annotations
import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
@dataclass(frozen=True, slots=True)
class ConnectionStatus:
    exchange: str; connected: bool; last_update: datetime | None = None; ping_ms: float | None = None
class WebSocketService:
    def __init__(self):
        self._statuses={}; self._threads={}; self._stop=threading.Event(); self.on_status: Callable[[ConnectionStatus],None] | None=None; self.on_message: Callable[[str,dict],None] | None=None
    def mark_update(self, exchange: str, ping_ms: float | None=None):
        self._statuses[exchange]=ConnectionStatus(exchange,True,datetime.now(timezone.utc),ping_ms); self._notify(exchange)
    def mark_disconnected(self, exchange: str):
        self._statuses[exchange]=ConnectionStatus(exchange,False); self._notify(exchange)
    def statuses(self): return dict(self._statuses)
    def start(self, exchange: str, url: str, subscribe: dict | list[dict] | None) -> None:
        if exchange in self._threads: return
        thread=threading.Thread(target=lambda: asyncio.run(self._run(exchange,url,subscribe)),daemon=True); self._threads[exchange]=thread; thread.start()
    def stop(self) -> None: self._stop.set(); self._threads.clear()
    async def _run(self, exchange, url, subscribe):
        import json
        import websockets
        while not self._stop.is_set():
            try:
                async with websockets.connect(url,ping_interval=20,ping_timeout=10) as socket:
                    if subscribe is not None:
                        await socket.send(json.dumps(subscribe))
                    self.mark_update(exchange)
                    while not self._stop.is_set():
                        started=time.perf_counter(); raw=await socket.recv(); self.mark_update(exchange,(time.perf_counter()-started)*1000)
                        if self.on_message:
                            try: self.on_message(exchange,json.loads(raw))
                            except json.JSONDecodeError: pass
            except Exception: self.mark_disconnected(exchange); await asyncio.sleep(5)
    def _notify(self, exchange):
        if self.on_status: self.on_status(self._statuses[exchange])
