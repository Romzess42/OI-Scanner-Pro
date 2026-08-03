"""Optional online license validation; disabled until a URL is configured."""
from __future__ import annotations
import json
from urllib.error import URLError
from urllib.request import urlopen
class LicenseService:
    def __init__(self, validation_url: str=""): self.validation_url=validation_url
    def validate(self, key: str) -> bool:
        if not self.validation_url or not key: return False
        try:
            with urlopen(f"{self.validation_url}?key={key}", timeout=10) as response:
                return bool(json.loads(response.read()).get("valid"))
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return False
