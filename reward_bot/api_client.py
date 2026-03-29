"""HTTP client for reward bot -> backend."""

from __future__ import annotations

import httpx
import logging

logger = logging.getLogger(__name__)

class BackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def get_dashboard(self, telegram_user_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{self.base_url}/dashboard/{telegram_user_id}")
            response.raise_for_status()
            return response.json()

    async def create_link(self, telegram_user_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/referral-links/create",
                json={"telegram_user_id": telegram_user_id},
            )
            response.raise_for_status()
            return response.json()

    async def claim(self, telegram_user_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{self.base_url}/rewards/{telegram_user_id}/claim")
            response.raise_for_status()
            return response.json()

    async def record_join_event(
        self,
        invited_telegram_user_id: int,
        invited_username: str | None,
        invited_first_name: str | None,
        invite_link: str,
    ) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/referral-events/record",
                json={
                    "invited_telegram_user_id": invited_telegram_user_id,
                    "invited_username": invited_username,
                    "invited_first_name": invited_first_name,
                    "invite_link": invite_link,
                },
            )
            response.raise_for_status()