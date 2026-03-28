"""HTTP client for verifier bot -> backend."""

from __future__ import annotations

import httpx


class BackendClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=20)

    async def verify_membership(self, telegram_user_id: int, username: str | None, first_name: str | None) -> dict:
        try:
            response = await self.client.post(
                    f"{self.base_url}/verify-membership",
                    json={
                        "telegram_user_id": telegram_user_id,
                        "username": username,
                        "first_name": first_name,
                    },
                )
        except Exception:
            return {
                "verified": False,
                "missing_items": [],
                "backend_error": "Verification service is unreachable. Please try again shortly.",
            }

        if response.status_code >= 400:
            detail = "Verification service unavailable."
            try:
                body = response.json()
                detail = body.get("detail", detail)
            except Exception:
                if response.text:
                    detail = response.text[:200]

            return {
                "verified": False,
                "missing_items": [],
                "backend_error": detail,
            }

        try:
            return response.json()
        except Exception:
            return {
                "verified": False,
                "missing_items": [],
                "backend_error": "Unexpected response from verification service.",
            }