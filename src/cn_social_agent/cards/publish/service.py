"""Orchestrate multi-platform card publish."""

from __future__ import annotations

from typing import Any, Optional

from cn_social_agent.cards.history import (
    append_publish_record,
    get_history_item,
    history_owner_key,
)
from cn_social_agent.cards.publish.images import list_export_images
from cn_social_agent.cards.publish.title import resolve_publish_title
from cn_social_agent.platforms import get_publisher


async def publish_card(
    *,
    history_id: str,
    platforms: list[str],
    direct: bool = False,
    title_override: str = "",
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    rec = get_history_item(history_id, user_id=user_id, email=email)
    if not rec:
        raise RuntimeError("历史记录不存在")

    cover = rec.get("cover") if isinstance(rec.get("cover"), dict) else {}
    title = (title_override or "").strip() or resolve_publish_title(cover)
    images = list_export_images(history_id)
    if not images:
        raise RuntimeError("请先导出或上传卡片图片")

    owner = history_owner_key(user_id=user_id, email=email)
    results: list[dict[str, Any]] = []
    for name in platforms:
        key = (name or "").strip().lower()
        if not key:
            continue
        try:
            pub = get_publisher(key)
        except KeyError:
            entry = {
                "platform": key,
                "status": "failed",
                "external_id": "",
                "url": "",
                "message": f"未知平台：{key}",
            }
            results.append(entry)
            append_publish_record(
                history_id, entry, user_id=user_id, email=email
            )
            continue

        result = await pub.publish(
            user_id=owner,
            title=title,
            image_paths=images,
            direct=direct,
            meta={
                "history_id": history_id,
                "email": email or "",
                "cover": cover,
                "knowledge": rec.get("knowledge") if isinstance(rec.get("knowledge"), list) else [],
                "brand_signature": str(
                    (rec.get("brand_signature") or cover.get("brand_signature") or "")
                ).strip(),
            },
        )
        results.append(result)
        append_publish_record(history_id, result, user_id=user_id, email=email)

    return {"title": title, "history_id": history_id, "results": results}
