from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from .ai_optimizer import optimize_idea_generation
from .connectors.base import RawMaterial

logger = logging.getLogger(__name__)


@dataclass
class IdeaCard:
    id: str
    material_id: str
    user_id: str
    title: str
    hook: str
    angles: list[str] = field(default_factory=list)
    heat_score: int = 0
    difficulty_score: int = 0
    time_window: str = "48h"
    content_type: str = "technical"
    status: str = "pending"
    feedback: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    selected_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


PROMPTS = {
    "technical": """你是一个技术内容选题专家。根据以下技术热点，生成一个技术解读选题。

技术热点：
- 项目名称：{title}
- 项目描述：{summary}
- Star 数量：{heat}
- 技术栈：{tags}

要求：
1. 标题吸引开发者，15字以内
2. Hook 要说明"为什么值得关注"
3. 角度要具体可执行

输出 JSON：
{{"title": "...", "hook": "...", "angles": ["...", "...", "..."]}}""",
    "opinion": """你是一个观点内容选题专家。根据以下话题，生成一个观点输出选题。

话题：
- 原文标题：{title}
- 原文摘要：{summary}
- 讨论热度：{heat}

要求：
1. 标题观点鲜明，引发讨论
2. Hook 要有争议性
3. 角度要包含正反方

输出 JSON：
{{"title": "...", "hook": "...", "angles": ["...", "...", "..."]}}""",
    "tutorial": """你是一个教程内容选题专家。根据以下痛点，生成一个教程选题。

痛点：
- 用户问题：{title}
- 相关技术：{summary}
- 出现频率：{heat}

要求：
1. 标题要说明"能学到什么"
2. Hook 要具体可量化
3. 角度要循序渐进

输出 JSON：
{{"title": "...", "hook": "...", "angles": ["...", "...", "..."]}}""",
    "news": """你是一个新闻解读选题专家。根据以下新闻，生成一个深度解读选题。

新闻：
- 标题：{title}
- 摘要：{summary}
- 关注度：{heat}

要求：
1. 标题要说明"影响是什么"
2. Hook 要有时效性
3. 角度要全面

输出 JSON：
{{"title": "...", "hook": "...", "angles": ["...", "...", "..."]}}""",
}


def _build_prompt(material: RawMaterial, content_type: str) -> str:
    template = PROMPTS.get(content_type, PROMPTS["technical"])
    return template.format(
        title=material.title,
        summary=material.summary or "无描述",
        heat=material.heat,
        tags=", ".join(material.tags[:5]),
    )


async def generate_idea_card(
    material: RawMaterial,
    user_id: str,
    llm_call=None,
) -> IdeaCard:
    optimization = optimize_idea_generation(material)
    content_type = optimization["content_type"]
    prompt = _build_prompt(material, content_type)

    if llm_call:
        try:
            response = await llm_call(prompt)
            result = _parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            result = _fallback_generation(material, optimization)
    else:
        result = _fallback_generation(material, optimization)

    card_id = f"card:{material.id}:{user_id}"

    return IdeaCard(
        id=card_id,
        material_id=material.id,
        user_id=user_id,
        title=result["title"],
        hook=result["hook"],
        angles=result.get("angles", optimization["angles"]),
        heat_score=optimization["heat_score"],
        difficulty_score=optimization["difficulty_score"],
        time_window=optimization["time_window"],
        content_type=content_type,
    )


def _parse_llm_response(response: str) -> dict[str, Any]:
    try:
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        return json.loads(json_str.strip())
    except Exception:
        return {}


def _fallback_generation(
    material: RawMaterial | None,
    optimization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if material:
        title = material.title[:15]
        hook = material.summary[:100] if material.summary else material.title
    else:
        title = "待定选题"
        hook = "需要进一步分析"

    angles = optimization["angles"] if optimization else ["角度1", "角度2", "角度3"]

    return {
        "title": title,
        "hook": hook,
        "angles": angles,
    }


async def batch_generate_cards(
    materials: list[RawMaterial],
    user_id: str,
    llm_call=None,
    max_concurrent: int = 5,
) -> list[IdeaCard]:
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _generate(material: RawMaterial) -> IdeaCard:
        async with semaphore:
            return await generate_idea_card(material, user_id, llm_call)

    tasks = [_generate(m) for m in materials]
    return await asyncio.gather(*tasks)
