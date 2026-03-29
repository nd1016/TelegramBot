"""HTTP client for verifier bot -> backend."""

from __future__ import annotations
import httpx

class BackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def verify_membership(self, telegram_user_id: int, username: str | None, first_name: str | None) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/verify-membership",
                json={
                    "telegram_user_id": telegram_user_id,
                    "username": username,
                    "first_name": first_name
                }
            )
            response.raise_for_status()
            return response.json()