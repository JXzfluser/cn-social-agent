"""Session/message persistence — InsForge PostgREST or in-memory for local/tests."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}" if prefix else uuid.uuid4().hex


def stable_user_id_for_email(email: str) -> str:
    """Deterministic id so memory-store restarts keep the same user key."""
    e = (email or "").strip().lower()
    if e == "demo@local.test":
        return "u_demo_local"
    digest = hashlib.sha256(e.encode("utf-8")).hexdigest()[:20]
    return f"u_{digest}"


class Store(ABC):
    @abstractmethod
    async def create_session(
        self,
        user_id: str,
        *,
        title: str = "New chat",
        system_prompt: str = "",
        model: str = "",
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def get_session(self, user_id: str, session_id: str) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    async def delete_session(self, user_id: str, session_id: str) -> bool: ...

    @abstractmethod
    async def update_session(
        self, user_id: str, session_id: str, **fields: Any
    ) -> Optional[dict[str, Any]]: ...

    @abstractmethod
    async def list_messages(self, user_id: str, session_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def add_message(
        self,
        user_id: str,
        session_id: str,
        *,
        role: str,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]: ...

    @abstractmethod
    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool) -> None: ...

    @abstractmethod
    async def get_skill_bindings(self, user_id: str) -> dict[str, bool]: ...

    @abstractmethod
    async def get_user_prefs(self, user_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def upsert_user_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def add_media(
        self, user_id: str, storage_path: str, mime: str
    ) -> dict[str, Any]: ...


class MemoryStore(Store):
    """Process-local store for tests and offline bootstrapping."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.skills: dict[str, dict[str, bool]] = {}
        self.prefs: dict[str, dict[str, Any]] = {}
        self.media: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, str]] = {}
        self.tokens: dict[str, str] = {}
        # Local demo account (UI defaults)
        self.register_user("demo@local.test", "demo123456")

    def ensure_demo_user(self) -> None:
        if "demo@local.test" not in self.users:
            self.register_user("demo@local.test", "demo123456")

    def register_user(self, email: str, password: str) -> dict[str, str]:
        email = (email or "").strip().lower()
        if email in self.users:
            return {"id": self.users[email]["id"], "email": email}
        user_id = stable_user_id_for_email(email)
        self.users[email] = {"id": user_id, "email": email, "password": password}
        return {"id": user_id, "email": email}

    def login_user(self, email: str, password: str) -> Optional[dict[str, str]]:
        email = (email or "").strip().lower()
        user = self.users.get(email)
        if not user or user["password"] != password:
            return None
        token = secrets.token_urlsafe(24)
        self.tokens[token] = user["id"]
        return {"accessToken": token, "user": {"id": user["id"], "email": email}}

    def user_id_for_token(self, token: str) -> Optional[str]:
        return self.tokens.get(token)

    async def create_session(
        self,
        user_id: str,
        *,
        title: str = "New chat",
        system_prompt: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        sid = new_id("s_")
        row = {
            "id": sid,
            "user_id": user_id,
            "title": title,
            "system_prompt": system_prompt,
            "model": model,
            "agent_state": {},
            "created_at": _now(),
            "updated_at": _now(),
        }
        self.sessions[sid] = row
        self.messages[sid] = []
        return row

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        rows = [s for s in self.sessions.values() if s["user_id"] == user_id]
        return sorted(rows, key=lambda r: r["updated_at"], reverse=True)

    async def get_session(self, user_id: str, session_id: str) -> Optional[dict[str, Any]]:
        row = self.sessions.get(session_id)
        if row and row["user_id"] == user_id:
            return row
        return None

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        row = await self.get_session(user_id, session_id)
        if not row:
            return False
        del self.sessions[session_id]
        self.messages.pop(session_id, None)
        return True

    async def update_session(
        self, user_id: str, session_id: str, **fields: Any
    ) -> Optional[dict[str, Any]]:
        row = await self.get_session(user_id, session_id)
        if not row:
            return None
        for key in ("title", "system_prompt", "model", "agent_state"):
            if key in fields and fields[key] is not None:
                row[key] = fields[key]
        row["updated_at"] = _now()
        return row

    async def list_messages(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        if not await self.get_session(user_id, session_id):
            return []
        return list(self.messages.get(session_id, []))

    async def add_message(
        self,
        user_id: str,
        session_id: str,
        *,
        role: str,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        if not await self.get_session(user_id, session_id):
            raise KeyError("session not found")
        msg = {
            "id": new_id("m_"),
            "session_id": session_id,
            "role": role,
            "content": content,
            "tool_calls": tool_calls,
            "created_at": _now(),
        }
        self.messages.setdefault(session_id, []).append(msg)
        self.sessions[session_id]["updated_at"] = _now()
        if role == "user" and self.sessions[session_id]["title"] == "New chat":
            self.sessions[session_id]["title"] = (content or "New chat")[:48]
        return msg

    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool) -> None:
        self.skills.setdefault(user_id, {})[skill_id] = enabled

    async def get_skill_bindings(self, user_id: str) -> dict[str, bool]:
        return dict(self.skills.get(user_id, {}))

    async def get_user_prefs(self, user_id: str) -> dict[str, Any]:
        from cn_social_agent.api.prefs import normalize_prefs

        return normalize_prefs(self.prefs.get(user_id))

    async def upsert_user_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        from cn_social_agent.api.prefs import normalize_prefs

        row = normalize_prefs(prefs)
        self.prefs[user_id] = row
        return dict(row)

    async def add_media(
        self, user_id: str, storage_path: str, mime: str
    ) -> dict[str, Any]:
        mid = new_id("media_")
        row = {
            "id": mid,
            "user_id": user_id,
            "storage_path": storage_path,
            "mime": mime,
            "created_at": _now(),
        }
        self.media[mid] = row
        return row


class InsForgeStore(Store):
    """Persist workbench data via InsForge PostgREST (`wb_*` tables)."""

    SESSIONS = "wb_sessions"
    MESSAGES = "wb_messages"
    SKILLS = "wb_skill_bindings"
    PREFS = "wb_user_prefs"
    MEDIA = "wb_media_objects"

    def __init__(self, db: Any) -> None:
        self.db = db

    async def create_session(
        self,
        user_id: str,
        *,
        title: str = "New chat",
        system_prompt: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "title": title,
            "system_prompt": system_prompt,
            "model": model,
        }
        created = await self.db.create(self.SESSIONS, row)
        return created[0] if created else row

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        return await self.db.query(
            self.SESSIONS,
            filters={"user_id": f"eq.{user_id}"},
            order="updated_at.desc",
        )

    async def get_session(self, user_id: str, session_id: str) -> Optional[dict[str, Any]]:
        row = await self.db.get_by_id(self.SESSIONS, session_id)
        if row and row.get("user_id") == user_id:
            raw = row.get("agent_state")
            if isinstance(raw, str) and raw.strip():
                try:
                    row = {**row, "agent_state": json.loads(raw)}
                except Exception:  # noqa: BLE001
                    pass
            return row
        return None

    async def delete_session(self, user_id: str, session_id: str) -> bool:
        if not await self.get_session(user_id, session_id):
            return False
        await self.db.delete(self.SESSIONS, filters={"id": f"eq.{session_id}"})
        await self.db.delete(self.MESSAGES, filters={"session_id": f"eq.{session_id}"})
        return True

    async def update_session(
        self, user_id: str, session_id: str, **fields: Any
    ) -> Optional[dict[str, Any]]:
        if not await self.get_session(user_id, session_id):
            return None
        payload = {
            k: v
            for k, v in fields.items()
            if k in ("title", "system_prompt", "model", "agent_state") and v is not None
        }
        # Serialize agent_state for PostgREST json/text columns
        if "agent_state" in payload and not isinstance(payload["agent_state"], str):
            payload["agent_state"] = json.dumps(payload["agent_state"], ensure_ascii=False)
        payload["updated_at"] = _now()
        try:
            updated = await self.db.update(
                self.SESSIONS, {"id": f"eq.{session_id}"}, payload
            )
            return updated[0] if updated else None
        except Exception:
            # Column may be missing — retry without agent_state
            if "agent_state" not in payload:
                raise
            payload.pop("agent_state", None)
            updated = await self.db.update(
                self.SESSIONS, {"id": f"eq.{session_id}"}, payload
            )
            return updated[0] if updated else None

    async def list_messages(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        if not await self.get_session(user_id, session_id):
            return []
        return await self.db.query(
            self.MESSAGES,
            filters={"session_id": f"eq.{session_id}"},
            order="created_at.asc",
        )

    async def add_message(
        self,
        user_id: str,
        session_id: str,
        *,
        role: str,
        content: str,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        if not await self.get_session(user_id, session_id):
            raise KeyError("session not found")
        row: dict[str, Any] = {
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        if tool_calls is not None:
            row["tool_calls"] = tool_calls
        created = await self.db.create(self.MESSAGES, row)
        await self.db.update(
            self.SESSIONS,
            {"id": f"eq.{session_id}"},
            {"updated_at": _now()},
        )
        if role == "user":
            session = await self.get_session(user_id, session_id)
            if session and session.get("title") in (None, "", "New chat"):
                await self.db.update(
                    self.SESSIONS,
                    {"id": f"eq.{session_id}"},
                    {"title": (content or "New chat")[:48]},
                )
        return created[0] if created else row

    async def set_skill_enabled(self, user_id: str, skill_id: str, enabled: bool) -> None:
        existing = await self.db.query(
            self.SKILLS,
            filters={"user_id": f"eq.{user_id}", "skill_id": f"eq.{skill_id}"},
            limit=1,
        )
        if existing:
            await self.db.update(
                self.SKILLS,
                {"id": f"eq.{existing[0]['id']}"},
                {"enabled": enabled},
            )
        else:
            await self.db.create(
                self.SKILLS,
                {"user_id": user_id, "skill_id": skill_id, "enabled": enabled},
            )

    async def get_skill_bindings(self, user_id: str) -> dict[str, bool]:
        rows = await self.db.query(
            self.SKILLS,
            filters={"user_id": f"eq.{user_id}"},
            limit=500,
        )
        return {r["skill_id"]: bool(r.get("enabled", True)) for r in rows}

    async def get_user_prefs(self, user_id: str) -> dict[str, Any]:
        from cn_social_agent.api.prefs import normalize_prefs
        from cn_social_agent.api.prefs_local import merge_extras

        try:
            rows = await self.db.query(
                self.PREFS,
                filters={"user_id": f"eq.{user_id}"},
                limit=1,
            )
        except Exception:  # noqa: BLE001 — table may not exist yet
            rows = []
        row = rows[0] if rows else {}
        return normalize_prefs(
            merge_extras(
                user_id,
                {
                    "default_audience": row.get("default_audience"),
                    "default_voice": row.get("default_voice"),
                    "default_content_angle": row.get("default_content_angle"),
                    "default_platform": row.get("default_platform"),
                    "recent_topics": row.get("recent_topics"),
                    "llm_mode": row.get("llm_mode"),
                    "llm_model": row.get("llm_model"),
                },
            )
        )

    async def upsert_user_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        from cn_social_agent.api.prefs import normalize_prefs
        from cn_social_agent.api.prefs_local import write_extras

        row = normalize_prefs(prefs)
        # `wb_user_prefs` has no column for connector / automation / canvas state
        write_extras(user_id, row)
        payload = {
            "user_id": user_id,
            "default_audience": row["default_audience"],
            "default_voice": row["default_voice"],
            "default_content_angle": row["default_content_angle"],
            "default_platform": row["default_platform"],
            "recent_topics": row["recent_topics"],
            "llm_mode": row["llm_mode"],
            "llm_model": row["llm_model"],
        }
        try:
            existing = await self.db.query(
                self.PREFS,
                filters={"user_id": f"eq.{user_id}"},
                limit=1,
            )
            if existing:
                await self.db.update(
                    self.PREFS,
                    {"id": f"eq.{existing[0]['id']}"},
                    payload,
                )
            else:
                await self.db.create(self.PREFS, payload)
        except Exception:  # noqa: BLE001
            # Persist failed (missing table) — still return normalized prefs for this request
            pass
        return row

    async def add_media(
        self, user_id: str, storage_path: str, mime: str
    ) -> dict[str, Any]:
        row = {
            "user_id": user_id,
            "storage_path": storage_path,
            "mime": mime,
        }
        created = await self.db.create(self.MEDIA, row)
        return created[0] if created else row
