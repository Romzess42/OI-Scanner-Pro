"""Optional version-manifest check; disabled until a URL is configured."""
from __future__ import annotations
import json
from urllib.error import URLError
from urllib.request import urlopen
class UpdateService:
    def __init__(self, manifest_url: str=""): self.manifest_url=manifest_url
    def latest_version(self) -> str | None:
        if not self.manifest_url: return None
        try:
            with urlopen(self.manifest_url, timeout=10) as response:
                value = json.loads(response.read()).get("version")
                return str(value) if value else None
        except (OSError, URLError, ValueError, json.JSONDecodeError):
            return None
