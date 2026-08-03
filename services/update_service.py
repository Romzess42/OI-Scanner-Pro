"""Optional version-manifest check; disabled until a URL is configured."""
from __future__ import annotations
import json
from urllib.request import urlopen
class UpdateService:
    def __init__(self, manifest_url: str=""): self.manifest_url=manifest_url
    def latest_version(self) -> str | None:
        if not self.manifest_url: return None
        with urlopen(self.manifest_url,timeout=10) as response: return json.loads(response.read()).get("version")
