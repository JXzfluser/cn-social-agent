from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import uuid


@dataclass
class Fragment:
    id: str
    user_id: str
    content: str
    fragment_type: str = "text"
    auto_tags: list[str] = field(default_factory=list)
    related_material_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "fragment_type": self.fragment_type,
            "auto_tags": self.auto_tags,
            "related_material_id": self.related_material_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def create(cls, user_id: str, content: str, fragment_type: str = "text") -> Fragment:
        return cls(
            id=f"frag:{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            content=content,
            fragment_type=fragment_type,
        )


class FragmentStore:
    def __init__(self):
        self._fragments: dict[str, list[Fragment]] = {}

    def add(self, fragment: Fragment) -> Fragment:
        user_id = fragment.user_id
        if user_id not in self._fragments:
            self._fragments[user_id] = []
        self._fragments[user_id].append(fragment)
        return fragment

    def get(self, user_id: str, fragment_id: str) -> Optional[Fragment]:
        fragments = self._fragments.get(user_id, [])
        for f in fragments:
            if f.id == fragment_id:
                return f
        return None

    def list(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        fragments = self._fragments.get(user_id, [])
        fragments.sort(key=lambda x: x.created_at, reverse=True)

        total = len(fragments)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [f.to_dict() for f in fragments[start:end]],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete(self, user_id: str, fragment_id: str) -> bool:
        fragments = self._fragments.get(user_id, [])
        for i, f in enumerate(fragments):
            if f.id == fragment_id:
                fragments.pop(i)
                return True
        return False

    def update_tags(self, user_id: str, fragment_id: str, tags: list[str]) -> bool:
        fragment = self.get(user_id, fragment_id)
        if fragment:
            fragment.auto_tags = tags
            return True
        return False


fragment_store = FragmentStore()
