from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import ConnectorConfig, IdeaConnector, RawMaterial


class KnowledgeBaseConnector(IdeaConnector):
    id = "knowledge_base"
    name = "知识库"
    description = "从本地知识库获取素材"
    icon = "📚"

    capabilities = {
        "source": True,
        "monitor": False,
        "realtime": False,
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.kb_path = config.extra.get("path", "knowledge")
        self.formats = config.extra.get("formats", ["md", "txt", "json"])

    async def fetch(self) -> list[RawMaterial]:
        materials = []
        kb_dir = Path(self.kb_path)

        if not kb_dir.exists():
            return materials

        for ext in self.formats:
            for file_path in kb_dir.rglob(f"*.{ext}"):
                try:
                    item = self._process_file(file_path)
                    if item:
                        materials.append(item)
                except Exception:
                    continue

        return materials[: self.config.max_items]

    def _process_file(self, file_path: Path) -> RawMaterial | None:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        if not content.strip():
            return None

        title = file_path.stem
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

        summary = content[:500] if len(content) > 500 else content

        tags = ["knowledge_base", file_path.suffix.lstrip(".")]

        relative_path = str(file_path.relative_to(Path.cwd())) if file_path.is_absolute() else str(file_path)

        keywords_lower = [k.lower() for k in self.config.keywords]
        if keywords_lower:
            text = f"{title} {content}".lower()
            if not any(k in text for k in keywords_lower):
                return None

        return RawMaterial(
            id=f"kb:{relative_path}",
            connector_id=self.id,
            source="knowledge_base",
            title=title,
            url=None,
            summary=summary,
            tags=tags,
            heat=0,
            raw_data={
                "file_path": relative_path,
                "file_size": file_path.stat().st_size,
                "file_type": file_path.suffix.lstrip("."),
            },
        )
