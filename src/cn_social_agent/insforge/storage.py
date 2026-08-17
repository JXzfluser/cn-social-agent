"""InsForge Storage API wrapper (aligned with vendor multipart + bucket schema)."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

import httpx

from .client import InsForgeClient, InsForgeError


class InsForgeStorage:
    """InsForge Storage API wrapper.

    Upload uses multipart field ``file`` (see PUT /api/storage/buckets/:bucket/objects/*).
    Create bucket uses ``{bucketName, isPublic}``.
    """

    def __init__(self, client: InsForgeClient):
        self._client = client
        self._api_base = client.config.api_url.rstrip("/")

    def _auth_headers(self) -> dict[str, str]:
        hdrs: dict[str, str] = {}
        if self._client._admin_token:
            hdrs["Authorization"] = f"Bearer {self._client._admin_token}"
        elif self._client._anon_key or self._client.config.anon_key:
            key = self._client._anon_key or self._client.config.anon_key
            hdrs["Authorization"] = f"Bearer {key}"
        return hdrs

    async def create_bucket(self, name: str, public: bool = False) -> dict[str, Any]:
        return await self._client.api_post(
            "/api/storage/buckets",
            json_body={"bucketName": name, "isPublic": public},
        )

    async def ensure_bucket(self, name: str, *, public: bool = False) -> str:
        """Create bucket if missing; ignore already-exists errors."""
        try:
            await self.create_bucket(name, public=public)
        except InsForgeError as exc:
            text = f"{exc} {exc.body or ''}".lower()
            if exc.status_code in (409, 400) or "already" in text or "exist" in text:
                return name
            raise
        return name

    async def list_buckets(self) -> list[dict[str, Any]]:
        result = await self._client.api_get("/api/storage/buckets")
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            data = result.get("data") or result.get("buckets") or []
            return data if isinstance(data, list) else []
        return []

    async def delete_bucket(self, name: str) -> None:
        await self._client.api_delete(f"/api/storage/buckets/{name}")

    async def upload(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: Optional[str] = None,
        upsert: bool = False,
        filename: Optional[str] = None,
    ) -> dict[str, Any]:
        if not content_type:
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        object_key = key.lstrip("/")
        if upsert:
            try:
                await self.delete_object(bucket, object_key)
            except Exception:  # noqa: BLE001
                pass

        url = f"{self._api_base}/api/storage/buckets/{bucket}/objects/{object_key}"
        fname = filename or Path(object_key).name or "upload.bin"
        files = {"file": (fname, data, content_type)}
        headers = self._auth_headers()
        # Do not set Content-Type — httpx sets multipart boundary.
        resp = await self._client._http.put(url, files=files, headers=headers)
        if resp.is_error:
            raise InsForgeError(
                f"upload failed ({resp.status_code}): {resp.text}",
                resp.status_code,
                resp.text,
            )
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = {}
        # Vendor wraps as { data: StorageFile, ... } or returns file directly
        payload = body.get("data") if isinstance(body, dict) and "data" in body else body
        if not isinstance(payload, dict):
            payload = {}
        return {
            "bucket": payload.get("bucket") or bucket,
            "key": payload.get("key") or object_key,
            "size": payload.get("size") or len(data),
            "mimeType": payload.get("mimeType") or content_type,
            "raw": payload,
        }

    async def upload_file(
        self,
        bucket: str,
        key: str,
        path: str | Path,
        *,
        content_type: Optional[str] = None,
        upsert: bool = True,
    ) -> dict[str, Any]:
        p = Path(path)
        data = p.read_bytes()
        ctype = content_type or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        return await self.upload(
            bucket, key, data, content_type=ctype, upsert=upsert, filename=p.name
        )

    async def download(self, bucket: str, key: str) -> bytes:
        url = f"{self._api_base}/api/storage/buckets/{bucket}/objects/{key.lstrip('/')}"
        async with self._client._http.stream(
            "GET",
            url,
            headers=self._auth_headers(),
        ) as resp:
            if resp.is_error:
                body = await resp.aread()
                raise InsForgeError(
                    f"download failed ({resp.status_code}): {body[:200]!r}",
                    resp.status_code,
                )
            return await resp.aread()

    async def delete_object(self, bucket: str, key: str) -> None:
        await self._client.api_delete(
            f"/api/storage/buckets/{bucket}/objects/{key.lstrip('/')}",
        )

    async def list_objects(self, bucket: str, prefix: str = "") -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if prefix:
            params["prefix"] = prefix
        result = await self._client.api_get(
            f"/api/storage/buckets/{bucket}/objects",
            params=params,
        )
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            data = result.get("data") or result.get("objects") or []
            return data if isinstance(data, list) else []
        return []

    async def get_download_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        path = f"/api/storage/buckets/{bucket}/download-strategy/objects/{key.lstrip('/')}"
        result = await self._client.api_get(path, params={"expiresIn": expires_in})
        if isinstance(result, dict):
            data = result.get("data") if isinstance(result.get("data"), dict) else result
            url = (data or {}).get("url") or (data or {}).get("downloadUrl") or ""
            if url:
                return str(url)
        return f"{self._api_base}/api/storage/buckets/{bucket}/objects/{key.lstrip('/')}"

    async def get_upload_url(
        self,
        bucket: str,
        *,
        filename: str,
        content_type: Optional[str] = None,
        size: Optional[int] = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"filename": filename}
        if content_type:
            body["contentType"] = content_type
        if size is not None:
            body["size"] = size
        result = await self._client.api_post(
            f"/api/storage/buckets/{bucket}/upload-strategy",
            json_body=body,
        )
        if isinstance(result, dict) and isinstance(result.get("data"), dict):
            return result["data"]
        return result if isinstance(result, dict) else {}

    async def s3_get_endpoint(self) -> dict[str, str]:
        return await self._client.api_get("/api/storage/s3/config")
