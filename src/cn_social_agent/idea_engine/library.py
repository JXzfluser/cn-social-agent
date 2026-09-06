from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid


@dataclass
class LibraryItem:
    id: str
    user_id: str
    card_id: str
    title: str
    hook: str
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "card_id": self.card_id,
            "title": self.title,
            "hook": self.hook,
            "tags": self.tags,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


class LibraryStore:
    def __init__(self):
        self._items: dict[str, list[LibraryItem]] = {}

    def add(self, item: LibraryItem) -> LibraryItem:
        user_id = item.user_id
        if user_id not in self._items:
            self._items[user_id] = []
        self._items[user_id].append(item)
        return item

    def get(self, user_id: str, item_id: str) -> Optional[LibraryItem]:
        items = self._items.get(user_id, [])
        for item in items:
            if item.id == item_id:
                return item
        return None

    def list(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        items = self._items.get(user_id, [])
        items.sort(key=lambda x: x.created_at, reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [item.to_dict() for item in items[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete(self, user_id: str, item_id: str) -> bool:
        items = self._items.get(user_id, [])
        for i, item in enumerate(items):
            if item.id == item_id:
                items.pop(i)
                return True
        return False

    def update(
        self,
        user_id: str,
        item_id: str,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> bool:
        item = self.get(user_id, item_id)
        if not item:
            return False
        if tags is not None:
            item.tags = tags
        if notes is not None:
            item.notes = notes
        return True

    def search(
        self,
        user_id: str,
        query: str,
    ) -> list[dict[str, Any]]:
        items = self._items.get(user_id, [])
        query_lower = query.lower()
        results = []
        for item in items:
            if (
                query_lower in item.title.lower()
                or query_lower in item.hook.lower()
                or any(query_lower in t.lower() for t in item.tags)
            ):
                results.append(item.to_dict())
        return results


library_store = LibraryStore()
