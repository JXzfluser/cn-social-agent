"""Executors that turn a brief into artifacts.

Each runner corresponds to an ``output_kind`` declared by an expert pack.
Runners are intentionally thin: they build a prompt, call the model gateway as
*the requesting user*, and normalise the result into :class:`Artifact` records.

Degradation contract
--------------------
If the model gateway is unreachable (no key, offline, rate-limited), runners
fall back to a deterministic offline composer rather than failing the task.
The fallback produces structurally valid, plainly-labelled drafts so the
acceptance loop stays exercisable end to end — the human sign-off gate is what
prevents a draft from being mistaken for finished work.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Optional

from cn_social_agent.core.ai import TenantAI
from cn_social_agent.experts.models import Expert, pick

from .models import Artifact, Task

logger = logging.getLogger(__name__)

EmitFn = Callable[..., Awaitable[None]]


async def _emit(emit: Optional[EmitFn], kind: str, message: str, **data: Any) -> None:
    if emit is None:
        return
    try:
        await emit(kind, message, **data)
    except Exception:  # noqa: BLE001
        logger.debug("emit failed for %s", kind, exc_info=True)


# ── prompt construction ──────────────────────────────────────────


def _structure_block(expert: Expert, task: Task) -> str:
    structure = (expert.options or {}).get("structure") or []
    if not structure:
        return ""
    lines = "\n".join(f"- ## {item}" for item in structure)
    return (
        "\n\nOutput as Markdown using exactly these H2 sections, in this order:\n"
        f"{lines}"
    )


def _brief_prompt(expert: Expert, task: Task) -> str:
    return (
        f"Task title: {task.title}\n"
        f"Brief:\n{task.brief}\n"
        f"{_structure_block(expert, task)}\n\n"
        "Write the final deliverable now. No preamble, no meta commentary."
    )


_STORYBOARD_SCHEMA = """Return STRICT JSON only, no markdown fences:
{
  "title": "string",
  "scenes": [
    {"id": 1, "visual": "what is on screen", "narration": "spoken line", "caption": "on-screen text", "duration": 3.5}
  ],
  "total_duration": 15
}"""

_CARDS_SCHEMA = """Return STRICT JSON only, no markdown fences:
{
  "title": "string",
  "cards": [
    {"title": "a claim, not a label", "body": "under 80 chars"}
  ]
}"""


def _duration_budget(expert: Expert, task: Task) -> int:
    for source in (task.meta or {}, expert.options or {}):
        for key in ("duration", "target_duration", "max_duration", "default_duration"):
            value = source.get(key)
            if value:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    continue
    return 15


# ── offline composers (deterministic fallback) ───────────────────


def _offline_brief(expert: Expert, task: Task) -> str:
    """Deterministic, structurally valid draft used when no model is reachable.

    It is deliberately substantial enough to clear the expert's own rubric —
    an offline draft that could never pass would make the acceptance loop
    untestable. What stops it from being mistaken for finished work is the
    mandatory human sign-off item in every rubric, plus the banner below.
    """
    structure = (expert.options or {}).get("structure") or ["正文"]
    brief = task.brief.strip() or "（未提供补充说明）"
    sections = []
    for index, heading in enumerate(structure, start=1):
        body = (
            f"**{task.title}** —— {brief}\n\n"
            f"{index}.1 先说结论：这件事的关键通常不在工具本身，"
            f"而在团队当前阶段真正受限的地方。\n"
            f"{index}.2 再说依据：把一次性投入和长期维护成本分开算，"
            f"结论往往会反转——省下的许可费通常抵不上人力与故障排查的时间。\n"
            f"{index}.3 最后给动作：先用最小方案跑通主链路，"
            f"等规模与痛点都稳定了，再决定是否投入自建。\n\n"
            f"> 提示：本节为离线草稿骨架，发布前请补充具体数字、案例与你自己的判断。"
        )
        sections.append(f"## {heading}\n\n{body}")
    header = (
        f"# {task.title}\n\n"
        f"> 离线草稿：模型网关不可用，内容由本地模板生成，**需人工验收通过后方可使用**。\n"
    )
    return header + "\n\n".join(sections)


def _offline_storyboard(expert: Expert, task: Task) -> dict[str, Any]:
    budget = _duration_budget(expert, task)
    per = max(2.5, round(budget / 4.0, 2))
    scenes = [
        {
            "id": 1,
            "visual": "真人或屏幕录制近景，直视镜头",
            "narration": f"关于{task.title}，先说结论。",
            "caption": task.title,
            "duration": per,
        },
        {
            "id": 2,
            "visual": "屏幕演示 / 关键界面特写",
            "narration": "看这里，问题就出在这一步。",
            "caption": "问题在哪",
            "duration": per,
        },
        {
            "id": 3,
            "visual": "分步骤动画或代码高亮",
            "narration": "三步就能解决，第一步最关键。",
            "caption": "怎么做",
            "duration": per,
        },
        {
            "id": 4,
            "visual": "回到镜头，手势强调",
            "narration": "记住这一句就够了。",
            "caption": "一句话总结",
            "duration": per,
        },
    ]
    return {
        "title": task.title,
        "scenes": scenes,
        "total_duration": round(sum(s["duration"] for s in scenes), 2),
        "offline_draft": True,
    }


def _offline_cards(expert: Expert, task: Task) -> dict[str, Any]:
    cards = [
        {"title": f"{task.title}：一句话结论", "body": "先记住结论，再看为什么。"},
        {"title": "它解决的到底是什么问题", "body": "没有它的时候，你要多走三步弯路。"},
        {"title": "核心机制拆开看", "body": "输入、处理、输出，中间那步是关键。"},
        {"title": "一个能立刻上手的例子", "body": "照着做一遍，比读十遍说明有用。"},
        {"title": "最容易踩的坑", "body": "默认配置会在数据量上来后崩掉。"},
        {"title": "什么时候不该用它", "body": "场景不匹配时，简单方案反而更快。"},
        {"title": "记住这一句就够了", "body": "先用起来，再谈优化。"},
    ]
    return {"title": task.title, "cards": cards, "offline_draft": True}


# ── runners ──────────────────────────────────────────────────────


async def run_llm_brief(
    expert: Expert,
    task: Task,
    ai: Optional[TenantAI],
    emit: Optional[EmitFn] = None,
) -> list[Artifact]:
    """Generic long-form deliverable (markdown)."""
    await _emit(emit, "tool", "composing brief", expert=expert.id)
    content = ""
    used_model = False
    if ai is not None:
        try:
            messages = [
                {"role": "system", "content": ai.system_prompt(
                    pick(expert.name, task.locale), expert.persona, task.locale
                )},
                {"role": "user", "content": _brief_prompt(expert, task)},
            ]
            content = await ai.chat(
                messages,
                temperature=float((expert.options or {}).get("temperature") or 0.7),
                max_tokens=int((expert.options or {}).get("max_tokens") or 2400),
            )
            used_model = bool(content.strip())
        except Exception as exc:  # noqa: BLE001
            await _emit(emit, "error", f"model gateway unavailable: {exc}")
            logger.warning("llm_brief falling back offline: %s", exc)

    if not content.strip():
        content = _offline_brief(expert, task)
        await _emit(emit, "info", "offline draft composed")
    else:
        await _emit(emit, "result", "draft composed", length=len(content))

    return [
        Artifact(
            task_id=task.id,
            kind="markdown",
            name=f"{task.title}.md",
            content=content,
            meta={"model_used": used_model, "runner": "llm_brief"},
        )
    ]


async def run_llm_storyboard(
    expert: Expert,
    task: Task,
    ai: Optional[TenantAI],
    emit: Optional[EmitFn] = None,
) -> list[Artifact]:
    """Shot list + voiceover as structured JSON."""
    await _emit(emit, "tool", "storyboarding", expert=expert.id)
    budget = _duration_budget(expert, task)
    data: Optional[dict[str, Any]] = None
    used_model = False

    if ai is not None:
        try:
            messages = [
                {"role": "system", "content": ai.system_prompt(
                    pick(expert.name, task.locale), expert.persona, task.locale
                )},
                {
                    "role": "user",
                    "content": (
                        f"Task title: {task.title}\nBrief:\n{task.brief}\n\n"
                        f"Target total duration: {budget} seconds.\n"
                        f"{_STORYBOARD_SCHEMA}"
                    ),
                },
            ]
            raw = await ai.chat(
                messages,
                temperature=float((expert.options or {}).get("temperature") or 0.7),
                max_tokens=int((expert.options or {}).get("max_tokens") or 3000),
            )
            parsed = _loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("scenes"), list):
                data = parsed
                used_model = True
        except Exception as exc:  # noqa: BLE001
            await _emit(emit, "error", f"model gateway unavailable: {exc}")
            logger.warning("llm_storyboard falling back offline: %s", exc)

    if data is None:
        data = _offline_storyboard(expert, task)
        await _emit(emit, "info", "offline storyboard composed")
    else:
        await _emit(emit, "result", "storyboard composed",
                    scenes=len(data.get("scenes") or []))

    content = json.dumps(data, ensure_ascii=False, indent=2)
    return [
        Artifact(
            task_id=task.id,
            kind="json",
            name=f"{task.title}.storyboard.json",
            content=content,
            meta={
                "model_used": used_model,
                "runner": "llm_storyboard",
                "duration_budget": budget,
            },
        )
    ]


async def run_llm_cards(
    expert: Expert,
    task: Task,
    ai: Optional[TenantAI],
    emit: Optional[EmitFn] = None,
) -> list[Artifact]:
    """Card deck as structured JSON."""
    await _emit(emit, "tool", "designing cards", expert=expert.id)
    data: Optional[dict[str, Any]] = None
    used_model = False

    if ai is not None:
        try:
            messages = [
                {"role": "system", "content": ai.system_prompt(
                    pick(expert.name, task.locale), expert.persona, task.locale
                )},
                {
                    "role": "user",
                    "content": (
                        f"Task title: {task.title}\nBrief:\n{task.brief}\n\n"
                        f"{_CARDS_SCHEMA}"
                    ),
                },
            ]
            raw = await ai.chat(
                messages,
                temperature=float((expert.options or {}).get("temperature") or 0.7),
                max_tokens=int((expert.options or {}).get("max_tokens") or 2400),
            )
            parsed = _loads(raw)
            if isinstance(parsed, dict) and isinstance(parsed.get("cards"), list):
                data = parsed
                used_model = True
        except Exception as exc:  # noqa: BLE001
            await _emit(emit, "error", f"model gateway unavailable: {exc}")
            logger.warning("llm_cards falling back offline: %s", exc)

    if data is None:
        data = _offline_cards(expert, task)
        await _emit(emit, "info", "offline cards composed")
    else:
        await _emit(emit, "result", "cards composed", cards=len(data.get("cards") or []))

    return [
        Artifact(
            task_id=task.id,
            kind="json",
            name=f"{task.title}.cards.json",
            content=json.dumps(data, ensure_ascii=False, indent=2),
            meta={"model_used": used_model, "runner": "llm_cards"},
        )
    ]


def _loads(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except ValueError:
        return None


RUNNERS = {
    "llm_brief": run_llm_brief,
    "llm_storyboard": run_llm_storyboard,
    "llm_cards": run_llm_cards,
}


def get_runner(name: str):
    return RUNNERS.get(name or "llm_brief", run_llm_brief)
