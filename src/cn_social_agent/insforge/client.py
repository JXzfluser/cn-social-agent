from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional
from urllib.parse import urljoin

import httpx

from .config import InsForgeConfig, load_config

logger = logging.getLogger(__name__)

# Stale keep-alive / upstream drop — retry after rebuilding the client.
_TRANSIENT_HTTPX = (
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.WriteError,
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
)


class InsForgeError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class InsForgeClient:
    """Low-level HTTP client for InsForge REST API."""

    def __init__(self, config: Optional[InsForgeConfig] = None):
        self.config = config or load_config()
        self._api_base = self.config.api_url.rstrip("/")
        self._auth_base = self.config.auth_url.rstrip("/")
        self._pgrst_base = self.config.postgrest_url.rstrip("/")
        self._admin_token: Optional[str] = None
        self._anon_key: Optional[str] = None
        self._http = self._new_http()

    def _new_http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(45.0, connect=15.0),
            follow_redirects=True,
            trust_env=False,
            # Shorter keep-alive reduces "server disconnected without response"
            # when PostgREST / gateway idle-closes pooled connections.
            limits=httpx.Limits(
                max_keepalive_connections=8,
                max_connections=32,
                keepalive_expiry=15.0,
            ),
        )

    async def _reset_http(self) -> None:
        old = self._http
        self._http = self._new_http()
        try:
            await old.aclose()
        except Exception:  # noqa: BLE001
            pass

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Auth helpers ─────────────────────────────────────────────

    async def admin_login(self) -> str:
        data = {
            "username": self.config.admin_username,
            "password": self.config.admin_password,
        }
        resp = await self._http.post(
            f"{self._api_base}/api/auth/admin/sessions",
            json=data,
        )
        if resp.is_error:
            raise InsForgeError(
                f"admin login failed: {resp.text}", resp.status_code
            )
        body = resp.json()
        self._admin_token = body.get("token") or body.get("accessToken")
        if not self._admin_token:
            raise InsForgeError("no token in admin login response")
        return self._admin_token

    async def get_anon_key(self) -> str:
        await self._ensure_admin_token()
        resp = await self._http.get(
            f"{self._api_base}/api/metadata/anon-key",
            headers=self._admin_headers,
        )
        if resp.is_error:
            raise InsForgeError(f"failed to get anon key: {resp.text}", resp.status_code)
        body: dict = resp.json()
        self._anon_key = str(body.get("anonKey") or body.get("accessToken") or "")
        return self._anon_key

    async def get_api_key(self) -> str:
        await self._ensure_admin_token()
        resp = await self._http.get(
            f"{self._api_base}/api/metadata/api-key",
            headers=self._admin_headers,
        )
        if resp.is_error:
            raise InsForgeError(f"failed to get api key: {resp.text}", resp.status_code)
        result: dict = resp.json()
        key = result.get("apiKey", "")
        return str(key) if key is not None else ""

    # ── Generic API helpers ──────────────────────────────────────

    async def api_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        use_auth: bool = True,
        base: str = "api",
    ) -> httpx.Response:
        base_url = self._api_base
        if base == "auth":
            base_url = self._auth_base
        elif base == "pgrst":
            base_url = self._pgrst_base

        url = urljoin(base_url + "/", path.lstrip("/"))

        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)

        if use_auth and self._admin_token:
            hdrs.setdefault("Authorization", f"Bearer {self._admin_token}")
        elif use_auth and (self._anon_key or self.config.anon_key):
            key = self._anon_key or self.config.anon_key
            hdrs.setdefault("Authorization", f"Bearer {key}")

        last_exc: Optional[BaseException] = None
        for attempt in range(3):
            try:
                return await self._http.request(
                    method.upper(),
                    url,
                    json=json_body,
                    params=params,
                    headers=hdrs,
                )
            except _TRANSIENT_HTTPX as exc:
                last_exc = exc
                logger.warning(
                    "InsForge %s %s transient %s (attempt %s/3): %s",
                    method.upper(),
                    path,
                    type(exc).__name__,
                    attempt + 1,
                    exc,
                )
                await self._reset_http()
                await asyncio.sleep(0.15 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    async def api_get(self, path: str, **kw) -> Any:
        resp = await self.api_request("GET", path, **kw)
        if resp.is_error:
            raise InsForgeError(f"GET {path} failed: {resp.text}", resp.status_code)
        return resp.json()

    async def api_post(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("POST", path, json_body=json_body, **kw)
        if resp.is_error:
            raise InsForgeError(f"POST {path} failed: {resp.text}", resp.status_code)
        # 204 No Content
        if resp.status_code == 204:
            return None
        return resp.json()

    async def api_put(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("PUT", path, json_body=json_body, **kw)
        if resp.is_error:
            raise InsForgeError(f"PUT {path} failed: {resp.text}", resp.status_code)
        if resp.status_code == 204:
            return None
        return resp.json()

    async def api_patch(self, path: str, json_body: Any = None, **kw) -> Any:
        resp = await self.api_request("PATCH", path, json_body=json_body, **kw)
        if resp.is_error:
            raise InsForgeError(f"PATCH {path} failed: {resp.text}", resp.status_code)
        if resp.status_code == 204:
            return None
        return resp.json()

    async def api_delete(self, path: str, **kw) -> None:
        resp = await self.api_request("DELETE", path, **kw)
        if resp.is_error:
            raise InsForgeError(f"DELETE {path} failed: {resp.text}", resp.status_code)

    # ── Internal ─────────────────────────────────────────────────

    async def _ensure_admin_token(self):
        if not self._admin_token:
            await self.admin_login()

    @property
    def _admin_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._admin_token}"} if self._admin_token else {}
