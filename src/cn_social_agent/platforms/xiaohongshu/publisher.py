"""Xiaohongshu half-auto publisher — carousel export + copy caption + creator center."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cn_social_agent.platforms.base import PublishResult

CREATOR_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publish"


def build_xhs_caption(
    *,
    title: str,
    cover: dict[str, Any] | None = None,
    knowledge: list[dict[str, Any]] | None = None,
    brand_signature: str = "",
) -> dict[str, str]:
    """Title + body + hashtags for Xiaohongshu note."""
    cover = cover or {}
    knowledge = knowledge or []
    tags = cover.get("tags") if isinstance(cover.get("tags"), list) else []
    tag_parts = [str(t).strip() for t in tags if str(t).strip()][:5]
    note_title = (title or "").strip() or " · ".join(tag_parts) or str(cover.get("title") or "知识卡片")
    note_title = note_title[:20]

    lines: list[str] = []
    thesis = str(cover.get("description") or cover.get("marketNote") or "").strip()
    if thesis:
        lines.append(thesis[:120])
    for i, k in enumerate(knowledge[:5], 1):
        if not isinstance(k, dict):
            continue
        tt = str(k.get("topicTitle") or "").strip()
        if not tt:
            continue
        lines.append(f"{i}. {tt}")
    if brand_signature.strip():
        lines.append("")
        lines.append(brand_signature.strip()[:40])
    body = "\n".join(lines).strip() or note_title

    hashtags = ["知识卡片", "干货分享"]
    for t in tag_parts[:3]:
        clean = re_sub_hash(t)
        if clean and clean not in hashtags:
            hashtags.append(clean)
    tag_line = " ".join(f"#{h}" for h in hashtags[:6])
    full = f"{body}\n\n{tag_line}".strip()
    return {
        "title": note_title,
        "body": body,
        "hashtags": tag_line,
        "caption": full,
        "creator_url": CREATOR_PUBLISH_URL,
    }


def re_sub_hash(s: str) -> str:
    import re

    return re.sub(r"[#\s]+", "", str(s or ""))[:12]


class XiaohongshuPublisher:
    """No OAuth — always ready for half-auto carousel publish."""

    name = "xiaohongshu"

    def auth_url(self, *, user_id: str, redirect_uri: str, state: str = "") -> str:
        sep = "&" if "?" in redirect_uri else "?"
        return f"{redirect_uri}{sep}code=half_auto&state={state}&platform=xiaohongshu"

    async def handle_callback(
        self, *, user_id: str, query: dict[str, str]
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "account": "xiaohongshu",
            "message": "小红书为半自动发布，无需 OAuth",
        }

    async def status(self, *, user_id: str) -> dict[str, Any]:
        return {
            "platform": "xiaohongshu",
            "ready": True,
            "authorized": True,
            "account": "半自动",
            "message": "导出图集 → 复制文案 → 打开创作者中心粘贴发布",
            "half_auto": True,
            "creator_url": CREATOR_PUBLISH_URL,
        }

    async def publish(
        self,
        *,
        user_id: str,
        title: str,
        image_paths: list[Path],
        direct: bool,
        meta: dict[str, Any],
    ) -> PublishResult:
        cover = meta.get("cover") if isinstance(meta.get("cover"), dict) else {}
        knowledge = meta.get("knowledge") if isinstance(meta.get("knowledge"), list) else []
        brand = str(meta.get("brand_signature") or "").strip()
        cap = build_xhs_caption(
            title=title,
            cover=cover,
            knowledge=knowledge,
            brand_signature=brand,
        )
        n = len(image_paths or [])
        paths = [str(p) for p in (image_paths or [])]
        msg = (
            f"半自动：已准备 {n} 张图集。请复制文案并打开创作者中心上传。"
            if n
            else "半自动：请先导出 PNG 图集，再复制文案发布。"
        )
        return {
            "platform": "xiaohongshu",
            "status": "draft",
            "external_id": "",
            "url": CREATOR_PUBLISH_URL,
            "message": msg,
            # Extra fields consumed by UI (TypedDict allows extras in practice via dict)
            "caption": cap.get("caption") or "",
            "title_text": cap.get("title") or title,
            "hashtags": cap.get("hashtags") or "",
            "image_count": n,
            "image_paths": paths,
            "half_auto": True,
            "creator_url": CREATOR_PUBLISH_URL,
        }  # type: ignore[return-value]
