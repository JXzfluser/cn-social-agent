"""Tenant-scoped object storage on InsForge Storage.

Two rules make storage isolation real rather than cosmetic:

1. **Key namespacing** — every object lives under ``<user_id>/...``. A path
   traversal or a forgotten filter cannot reach another tenant's prefix.
2. **User-scoped uploads** — objects are written with the *end user's* JWT, not
   the admin token. InsForge stamps the object row with that user as owner and
   enforces visibility for private buckets through the same identity used for
   RLS. Uploading as admin would make the object invisible (or globally
   visible) to the wrong principal.
"""

from __future__ import annotations

import logging
import mimetypes
import re
from pathlib import PurePosixPath
from typing import Any, Optional

from .tenant import require

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "nexus-assets"

_SAFE_KEY = re.compile(r"^[A-Za-z0-9._\-/]+$")


class StorageError(RuntimeError):
    pass


class TenantStorage:
    """Per-user object storage backed by an InsForge private bucket."""

    def __init__(self, client: Any, bucket: str = DEFAULT_BUCKET) -> None:
        self._client = client
        self.bucket = bucket

    # ── key handling ─────────────────────────────────────────────

    @staticmethod
    def _validate_key(key: str) -> str:
        cleaned = str(key).strip().lstrip("/")
        if not cleaned:
            raise StorageError("empty object key")
        # Reject traversal before it can escape the tenant prefix.
        parts = []
        for part in PurePosixPath(cleaned).parts:
            if part in ("..", "."):
                raise StorageError(f"illegal path segment in object key: {part!r}")
            parts.append(part)
        safe = "/".join(parts)
        if not _SAFE_KEY.match(safe):
            raise StorageError(f"object key contains unsafe characters: {key!r}")
        return safe

    def scoped_key(self, key: str) -> str:
        """Prefix a user-supplied key with the tenant namespace."""
        tenant = require()
        return f"{tenant.user_id}/{self._validate_key(key)}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {require().token}"}

    def _url(self, suffix: str = "") -> str:
        base = self._client.config.api_url.rstrip("/")
        return f"{base}/api/storage/buckets/{self.bucket}/objects{suffix}"

    # ── bucket ───────────────────────────────────────────────────

    async def ensure_bucket(self, public: bool = False) -> None:
        """Create the private bucket (admin operation, provisioning only)."""
        await self._client._ensure_admin_token()
        try:
            await self._client.api_post(
                "/api/storage/buckets",
                json_body={"bucketName": self.bucket, "isPublic": public},
                use_auth=True,
            )
        except Exception as exc:  # noqa: BLE001
            text = str(exc).lower()
            if "already" in text or "exist" in text:
                return
            logger.warning("bucket %s ensure failed: %s", self.bucket, exc)

    # ── objects ──────────────────────────────────────────────────

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        *,
        filename: Optional[str] = None,
    ) -> str:
        """Upload as the current user; returns the stored (namespaced) key."""
        full_key = self.scoped_key(key)
        ctype = content_type or mimetypes.guess_type(full_key)[0] or "application/octet-stream"
        name = filename or PurePosixPath(full_key).name or "upload.bin"
        files = {"file": (name, data, ctype)}
        resp = await self._client._http.put(
            f"{self._url()}/{full_key}",
            files=files,
            headers=self._headers(),
        )
        if resp.is_error:
            raise StorageError(f"upload failed ({resp.status_code}): {resp.text}")
        return full_key

    async def download(self, key: str) -> bytes:
        """Fetch an object as the current user (server-side proxying)."""
        full_key = self.scoped_key(key)
        resp = await self._client._http.get(
            f"{self._url()}/{full_key}", headers=self._headers()
        )
        if resp.is_error:
            raise StorageError(f"download failed ({resp.status_code}): {resp.text}")
        return resp.content

    async def delete(self, key: str) -> None:
        full_key = self.scoped_key(key)
        resp = await self._client._http.delete(
            f"{self._url()}/{full_key}", headers=self._headers()
        )
        if resp.is_error:
            raise StorageError(f"delete failed ({resp.status_code}): {resp.text}")

    async def list_objects(self, prefix: str = "") -> list[dict[str, Any]]:
        """List objects under the tenant namespace (plus optional sub-prefix)."""
        tenant = require()
        scoped = f"{tenant.user_id}/" + (self._validate_key(prefix) + "/" if prefix else "")
        resp = await self._client._http.get(
            self._url(),
            params={"prefix": scoped},
            headers=self._headers(),
        )
        if resp.is_error:
            raise StorageError(f"list failed ({resp.status_code}): {resp.text}")
        try:
            data = resp.json()
        except Exception:  # noqa: BLE001
            return []
        if isinstance(data, list):
            return data
        for key in ("objects", "data", "items"):
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, list):
                return value
        return []

    async def public_url(self, key: str) -> str:
        """Return the gateway download URL (requires the caller's own JWT)."""
        full_key = self.scoped_key(key)
        return f"{self._url()}/{full_key}"


def tenant_storage(client: Any, bucket: str = DEFAULT_BUCKET) -> TenantStorage:
    return TenantStorage(client, bucket)
