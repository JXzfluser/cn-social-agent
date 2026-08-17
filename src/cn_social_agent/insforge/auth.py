from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .client import InsForgeClient


@dataclass
class InsForgeUser:
    id: str
    email: str
    username: str = ""
    role: str = "authenticated"
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    raw: Optional[dict[str, Any]] = None


class InsForgeAuth:
    """InsForge Authentication API wrapper.

    Maps to InsForge client endpoints:
      POST /api/auth/register
      POST /api/auth/login
      POST /api/auth/logout
      GET  /api/auth/user
      POST /api/auth/refresh
    """

    def __init__(self, client: InsForgeClient):
        self._client = client

    async def register(self, email: str, password: str, **extra) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/auth/users?client_type=server",
            json_body={"email": email, "password": password, **extra},
            use_auth=True,
        )

    async def login(self, email: str, password: str) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/auth/sessions?client_type=server",
            json_body={"email": email, "password": password},
            use_auth=False,
        )

    async def get_current_user(self, token: str) -> Optional[InsForgeUser]:
        try:
            data = await self._client.api_get(
                "/api/auth/sessions/current",
                headers={"Authorization": f"Bearer {token}"},
                use_auth=False,
            )
            # Response wraps user in {"user": {...}} key
            user_data = data.get("user", data)
            return self._parse_user(user_data)
        except Exception:
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[InsForgeUser]:
        try:
            data = await self._client.api_get(f"/api/admin/users/{user_id}")
            return self._parse_user(data)
        except Exception:
            return None

    async def list_users(self, page: int = 1, limit: int = 50) -> list[InsForgeUser]:
        data = await self._client.api_get(
            "/api/admin/users",
            params={"page": page, "limit": limit},
        )
        users = data if isinstance(data, list) else data.get("users", [])
        return [self._parse_user(u) for u in users]

    async def delete_user(self, user_id: str) -> None:
        await self._client.api_delete(f"/api/admin/users/{user_id}")

    async def send_password_reset(self, email: str) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/auth/reset-password",
            json_body={"email": email},
            use_auth=False,
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/auth/refresh?client_type=server",
            json_body={"refreshToken": refresh_token},
            use_auth=False,
        )

    async def logout(self, access_token: str) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/auth/logout",
            json_body={"accessToken": access_token},
            headers={"Authorization": f"Bearer {access_token}"},
            use_auth=False,
        )

    async def health(self) -> bool:
        try:
            await self._client.api_get("/api/health", use_auth=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_user(data: dict[str, Any]) -> InsForgeUser:
        return InsForgeUser(
            id=data.get("id", ""),
            email=data.get("email", ""),
            username=data.get("username") or data.get("email", "").split("@")[0],
            role=data.get("role", "authenticated"),
            is_active=data.get("isActive", data.get("is_active", True)),
            raw=data,
        )
