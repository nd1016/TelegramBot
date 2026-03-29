"""HTTP client for welcome bot -> backend."""

from __future__ import annotations

import httpx


class BackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=20)

    async def get_welcome_settings(self, chat_id: str) -> dict:
        response = await self.client.get(f"{self.base_url}/welcome-settings/{chat_id}")
        response.raise_for_status()
        return response.json()
