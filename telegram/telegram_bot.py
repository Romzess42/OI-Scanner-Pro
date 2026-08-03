"""Minimal opt-in Telegram sender for scanner alerts."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TelegramNotifier:
    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = token.strip()
        self.chat_id = chat_id.strip()

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        if not self.enabled:
            return False
        request = Request(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            data=urlencode({"chat_id": self.chat_id, "text": message}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                return bool(json.loads(response.read().decode("utf-8")).get("ok"))
        except (OSError, ValueError):
            return False
