from __future__ import annotations

import hashlib
import time
from typing import Any, Optional


class Cache:
    def __init__(self, ttl_seconds: int = 3600):
        self._store: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None

        value, timestamp = self._store[key]
        if time.time() - timestamp > self._ttl:
            del self._store[key]
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (value, time.time())

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def cleanup(self) -> int:
        now = time.time()
        expired = [
            key for key, (_, timestamp) in self._store.items()
            if now - timestamp > self._ttl
        ]
        for key in expired:
            del self._store[key]
        return len(expired)


class MaterialCache:
    def __init__(self, ttl_seconds: int = 3600):
        self._cache = Cache(ttl_seconds)
        self._seen_hashes: set[str] = set()

    def _make_hash(self, material_data: dict[str, Any]) -> str:
        key = f"{material_data.get('source', '')}:{material_data.get('title', '')}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, material_data: dict[str, Any]) -> bool:
        h = self._make_hash(material_data)
        return h in self._seen_hashes

    def mark_seen(self, material_data: dict[str, Any]) -> None:
        h = self._make_hash(material_data)
        self._seen_hashes.add(h)

    def get_connector_cache(self, connector_id: str, user_id: str) -> Optional[list]:
        key = f"connector:{connector_id}:{user_id}"
        return self._cache.get(key)

    def set_connector_cache(
        self, connector_id: str, user_id: str, materials: list
    ) -> None:
        key = f"connector:{connector_id}:{user_id}"
        self._cache.set(key, materials)

    def cleanup(self) -> int:
        return self._cache.cleanup()


material_cache = MaterialCache()
