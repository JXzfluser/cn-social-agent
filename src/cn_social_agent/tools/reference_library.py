"""参考资料库（对标 OpenWorkBuddy data/library/）。

按用户隔离、**文件持久化**：HTTP 路由（上传/管理）与 agent 工具
（library_list / library_read）共用同一份单例。数据落
``data/library/{user_id}.json``，服务重启不丢。
"""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 200 * 1024          # 单文件 ≤200KB（文本）
MAX_FILES_PER_USER = 50              # 每用户文件数上限
MAX_USER_TOTAL_BYTES = 5 * 1024 * 1024  # 每用户总容量 ≤5MB

_TEXT_EXT_RE = re.compile(
    r"\.(txt|md|markdown|csv|tsv|json|log|py|js|ts|java|go|rs|c|cpp|h|sh|yaml|yml|xml|html|css|sql)$",
    re.IGNORECASE,
)


def _root() -> Path:
    override = (os.getenv("LIBRARY_DATA_DIR") or "").strip()
    if override:
        return Path(override)
    # 默认项目根/data/library（本文件位于 src/cn_social_agent/tools/）
    here = Path(__file__).resolve()
    project_root = here.parents[3] if (here.parents[3] / "data").is_dir() else here.parents[2]
    return project_root / "data" / "library"


def _safe_key(raw: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_@.+-]+", "_", (raw or "").strip().lower())[:96] or "anon"


class LibraryError(Exception):
    pass


class ReferenceLibrary:
    def __init__(self) -> None:
        self._items: dict[str, list[dict[str, Any]]] = {}
        self._loaded: set[str] = set()

    def _path(self, user_id: str) -> Path:
        return _root() / (_safe_key(user_id) + ".json")

    def _persist(self, user_id: str) -> None:
        try:
            path = self._path(user_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._items.get(user_id, []), ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001 — 落盘失败不阻断内存操作
            pass

    def _bucket(self, user_id: str) -> list[dict[str, Any]]:
        user_id = (user_id or "").strip()
        if user_id not in self._loaded:
            self._loaded.add(user_id)
            items: list[dict[str, Any]] = []
            try:
                path = self._path(user_id)
                if path.is_file():
                    raw = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        items = [i for i in raw if isinstance(i, dict) and i.get("id")]
            except Exception:  # noqa: BLE001 — 坏文件当作空库
                items = []
            self._items[user_id] = items
        return self._items.setdefault(user_id, [])

    def add(self, user_id: str, name: str, content: str) -> dict[str, Any]:
        user_id = (user_id or "").strip()
        name = (name or "").strip()
        if not user_id:
            raise LibraryError("user required")
        if not name:
            raise LibraryError("文件名不能为空")
        if not _TEXT_EXT_RE.search(name):
            raise LibraryError("仅支持文本类文件（md/txt/csv/json/代码等）")
        if not isinstance(content, str) or not content.strip():
            raise LibraryError("内容不能为空")
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise LibraryError("文件过大（>200KB）")
        bucket = self._bucket(user_id)
        if len(bucket) >= MAX_FILES_PER_USER:
            raise LibraryError(f"资料数量已达上限（{MAX_FILES_PER_USER} 个），请先删除部分资料")
        used = sum(len(i["content"].encode("utf-8")) for i in bucket)
        if used + len(data) > MAX_USER_TOTAL_BYTES:
            raise LibraryError("资料库总容量已满（5MB），请先清理")
        if any(i["name"] == name for i in bucket):
            raise LibraryError(f"同名资料已存在：{name}")
        item = {
            "id": "lib_" + secrets.token_hex(8),
            "user_id": user_id,
            "name": name,
            "kind": (name.rsplit(".", 1)[-1] if "." in name else "txt").lower(),
            "size": len(data),
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bucket.append(item)
        self._persist(user_id)
        return self._meta(item)

    def list(self, user_id: str) -> list[dict[str, Any]]:
        bucket = self._bucket((user_id or "").strip())
        return [self._meta(i) for i in sorted(bucket, key=lambda x: x["created_at"], reverse=True)]

    def get(self, user_id: str, item_id: str) -> dict[str, Any] | None:
        for i in self._bucket((user_id or "").strip()):
            if i["id"] == item_id:
                return i
        return None

    def search(self, user_id: str, query: str) -> dict[str, Any] | None:
        """按名称/内容模糊匹配（agent library_read 用）。"""
        bucket = self._bucket((user_id or "").strip())
        q = (query or "").strip().lower()
        if not q:
            return None
        for i in bucket:  # 先按文件名匹配
            if q in i["name"].lower():
                return i
        for i in bucket:  # 再按内容匹配
            if q in i["content"].lower():
                return i
        return None

    def delete(self, user_id: str, item_id: str) -> bool:
        bucket = self._bucket((user_id or "").strip())
        for idx, i in enumerate(bucket):
            if i["id"] == item_id:
                bucket.pop(idx)
                self._persist(user_id)
                return True
        return False

    @staticmethod
    def _meta(item: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in item.items() if k != "content"}

    def retrieve(self, user_id: str, query: str, *, top_k: int = 2, snippet_chars: int = 900) -> list[dict[str, Any]]:
        """轻量 RAG：滑窗 bigram 覆盖率打分，返回最相关的资料片段（中文友好，无需向量库）。

        整句打分会被无关内容稀释，因此对 query 做 8 字滑窗，取窗口级覆盖率的
        最大值作为该资料的得分——只要 query 中某一段与资料强相关即命中。
        """
        q = (query or "").strip()
        bucket = self._bucket((user_id or "").strip())
        if not q or not bucket:
            return []
        def bigrams(s: str) -> set[str]:
            s = re.sub(r"\s+", "", s.lower())
            return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else {s}
        qb = bigrams(q)
        # query 滑窗（步长 2、窗长 8），保证局部强相关的片段不被整句稀释
        q_clean = re.sub(r"\s+", "", q)
        windows: list[set[str]] = [qb]
        if len(q_clean) > 8:
            for start in range(0, len(q_clean) - 7, 2):
                windows.append(bigrams(q_clean[start:start + 8]))
        scored: list[tuple[float, dict[str, Any]]] = []
        for i in bucket:
            ib = bigrams(i["name"] + " " + i["content"][:4000])
            if not ib:
                continue
            best = 0.0
            for wb in windows:
                if not wb:
                    continue
                best = max(best, len(wb & ib) / len(wb))
            if best >= 0.35:
                scored.append((best, i))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, item in scored[:top_k]:
            content = item["content"]
            pos = content.lower().find(q[:8].lower()) if len(q) >= 4 else -1
            start = max(0, (pos - 100) if pos >= 0 else 0)
            snippet = content[start:start + snippet_chars]
            out.append({
                "id": item["id"],
                "name": item["name"],
                "score": round(score, 3),
                "snippet": snippet,
                "truncated": len(content) > start + snippet_chars,
            })
        return out


reference_library = ReferenceLibrary()
