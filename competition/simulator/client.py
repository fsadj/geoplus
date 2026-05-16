from __future__ import annotations

import json
import urllib.request

from .config import SimulatorConfig


class GPTMessagesClient:
    def __init__(self, config: SimulatorConfig) -> None:
        self.config = config

    def _api_url(self) -> str:
        if self.config.base_url.endswith("/v1/messages"):
            return self.config.base_url
        return f"{self.config.base_url}/v1/messages"

    def call(self, *, model: str, system: str, user: str, max_tokens: int) -> str:
        budget_tokens = max_tokens - 2000 if max_tokens > 4000 else max_tokens // 2
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "thinking": {"type": "enabled", "budget_tokens": budget_tokens},
        }
        request = urllib.request.Request(
            self._api_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": self.config.auth_token,
                "Authorization": f"Bearer {self.config.auth_token}",
            },
            method="POST",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler())
        with opener.open(request, timeout=self.config.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            data = json.loads(response.read().decode(charset))
        if data.get("error"):
            error = data["error"]
            if isinstance(error, dict):
                raise RuntimeError(error.get("message") or json.dumps(error, ensure_ascii=False))
            raise RuntimeError(str(error))
        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(part for part in text_parts if part).strip()
