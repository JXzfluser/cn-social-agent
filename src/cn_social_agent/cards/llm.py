"""LLM card generation (OpenAI-compatible or workbench LLM client)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from cn_social_agent.cards.build import clip_complete, normalize_llm_payload, now_label
from cn_social_agent.cards.categories import get_category
from cn_social_agent.cards.evidence import selected_evidences
from cn_social_agent.cards.scrape import filter_snippets

_MAX_TOKENS = 8192
_TEMPERATURE = 0.35


async def call_openai_compatible(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    base = (base_url or "https://api.deepseek.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    payload = {
        "model": model or "deepseek-chat",
        "messages": messages,
        "temperature": _TEMPERATURE,
        "max_tokens": _MAX_TOKENS,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120.0, trust_env=True) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        data = r.json()
        if r.status_code >= 400:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {data}")
        if data.get("error"):
            raise RuntimeError(f"LLM error: {data['error']}")
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        if not content:
            raise RuntimeError("LLM 返回为空")
        return str(content)


async def call_workbench_llm(llm: Any, messages: list[dict[str, str]], model: str = "") -> str:
    data = await llm.chat_completion(
        messages,
        model=model or "",
        max_tokens=_MAX_TOKENS,
        temperature=_TEMPERATURE,
    )
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError("Workbench LLM 返回为空")
    return str(content)


def _strip_code_fence(content: str) -> str:
    text = (content or "").strip()
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _repair_json_text(raw: str) -> str:
    """Best-effort fixes for common LLM JSON mistakes."""
    s = raw.strip()
    s = (
        s.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\uff02", '"')
    )
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    s = re.sub(r"(?m)^\s*//.*?$", "", s)
    s = re.sub(r"/\*[\s\S]*?\*/", "", s)
    return s.strip()


def _escape_newlines_in_strings(s: str) -> str:
    out: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                out.append(ch)
                esc = False
                continue
            if ch == "\\":
                out.append(ch)
                esc = True
                continue
            if ch == '"':
                in_str = False
                out.append(ch)
                continue
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def _extract_json_object(content: str) -> str:
    text = _strip_code_fence(content)
    start = text.find("{")
    if start < 0:
        return text
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    # Truncated: take from first { and close later
    return text[start:]


def _json_stack_state(text: str) -> tuple[list[str], bool]:
    """Return (bracket stack, currently_in_string)."""
    in_str = False
    esc = False
    stack: list[str] = []
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()
    return stack, in_str


def _strip_dangling_json_tail(text: str) -> str:
    """Remove incomplete keys / empty openers; keep valid trailing array strings."""
    for _ in range(8):
        prev = text
        text = re.sub(r",\s*$", "", text)
        stack, _ = _json_stack_state(text)
        top = stack[-1] if stack else ""
        if top == "{":
            # incomplete key without colon
            text2 = re.sub(r'([,{])\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*$', r"\1", text)
            if text2 != text:
                text = text2
            else:
                # key with colon but no value
                text = re.sub(r'([,{])\s*"[^"\\]*(?:\\.[^"\\]*)*"\s*:\s*$', r"\1", text)
                text = re.sub(r":\s*$", "", text)
        text = re.sub(r",\s*$", "", text)
        # drop empty open object at end: ...{
        if text.rstrip().endswith("{"):
            # only if that { is unmatched opener (already on stack)
            text = re.sub(r"\{\s*$", "", text)
            text = re.sub(r",\s*$", "", text)
        if text == prev:
            break
    return text


def _close_truncated_json(s: str) -> str:
    """Close open strings / arrays / objects when the model output was cut off."""
    text = s.rstrip()
    if not text:
        return text

    stack, in_str = _json_stack_state(text)
    if in_str:
        text += '"'

    text = _strip_dangling_json_tail(text)
    stack, in_str = _json_stack_state(text)
    if in_str:
        text += '"'
        text = _strip_dangling_json_tail(text)
        stack, _ = _json_stack_state(text)

    while stack:
        opener = stack.pop()
        text += "]" if opener == "[" else "}"
    return text


def _salvage_cover_and_knowledge(raw: str) -> dict[str, Any] | None:
    """Extract cover / complete knowledge objects even from badly truncated JSON."""
    text = _strip_code_fence(raw)
    out: dict[str, Any] = {}
    cover_m = re.search(
        r'"cover"\s*:\s*(\{(?:[^{}]|\{[^{}]*\})*\})',
        text,
        flags=re.S,
    )
    if cover_m:
        cov = _try_load(cover_m.group(1))
        if cov and isinstance(cov, dict):
            # _try_load expects top-level cover|knowledge; wrap if needed
            if "title" in cov or "description" in cov or "tags" in cov:
                out["cover"] = cov
            elif "cover" in cov:
                out["cover"] = cov["cover"]

    # Prefer closed truncated whole doc
    closed = _try_load(_extract_json_object(text))
    if closed:
        if "cover" in closed and "cover" not in out:
            out["cover"] = closed["cover"]
        if isinstance(closed.get("knowledge"), list):
            out["knowledge"] = [
                k
                for k in closed["knowledge"]
                if isinstance(k, dict) and (k.get("topicTitle") or k.get("concept") or k.get("keyPoint"))
            ]

    if "knowledge" not in out:
        knowledge: list[dict[str, Any]] = []
        for m in re.finditer(r'\{[^{}]*"topicTitle"\s*:\s*"[^"]+"[^{}]*\}', text, flags=re.S):
            item = _try_load(m.group(0))
            if item and isinstance(item, dict) and item.get("topicTitle"):
                knowledge.append(item)
        if knowledge:
            out["knowledge"] = knowledge

    if out.get("cover") or out.get("knowledge"):
        out.setdefault("cover", {})
        out.setdefault("knowledge", [])
        return out
    return None


def _try_load(cand: str) -> dict[str, Any] | None:
    if not cand:
        return None
    variants = [
        cand,
        _repair_json_text(cand),
        _escape_newlines_in_strings(cand),
        _escape_newlines_in_strings(_repair_json_text(cand)),
        _close_truncated_json(cand),
        _close_truncated_json(_repair_json_text(cand)),
        _close_truncated_json(_escape_newlines_in_strings(_repair_json_text(cand))),
    ]
    seen: set[str] = set()
    for v in variants:
        if not v or v in seen:
            continue
        seen.add(v)
        try:
            parsed = json.loads(v)
            if isinstance(parsed, dict) and ("cover" in parsed or "knowledge" in parsed):
                return parsed
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    return None


def _parse_json_content(content: str) -> dict[str, Any]:
    raw = _extract_json_object(content)
    parsed = _try_load(raw)
    if parsed is not None:
        return parsed
    repaired_full = _repair_json_text(_strip_code_fence(content))
    parsed = _try_load(_extract_json_object(repaired_full))
    if parsed is not None:
        return parsed
    salvaged = _salvage_cover_and_knowledge(content)
    if salvaged is not None:
        return salvaged
    preview = (raw or content or "")[:180].replace("\n", "\\n")
    raise RuntimeError(f"LLM JSON 解析失败；片段: {preview}")


async def _complete(
    *,
    messages: list[dict[str, str]],
    ai: dict[str, Any],
    workbench_llm: Any,
    workbench_model: str,
) -> str:
    api_key = str(ai.get("apiKey") or ai.get("api_key") or "").strip()
    if api_key:
        return await call_openai_compatible(
            base_url=str(ai.get("baseUrl") or ai.get("base_url") or "https://api.deepseek.com/v1"),
            api_key=api_key,
            model=str(ai.get("model") or "deepseek-chat"),
            messages=messages,
        )
    if workbench_llm is not None:
        return await call_workbench_llm(workbench_llm, messages, model=workbench_model)
    raise RuntimeError("未配置 AI：请在工作台设置中选择 LLM（含 InsForge）")


async def _complete_json(
    *,
    messages: list[dict[str, str]],
    ai: dict[str, Any],
    workbench_llm: Any,
    workbench_model: str,
) -> dict[str, Any]:
    content = await _complete(
        messages=messages,
        ai=ai,
        workbench_llm=workbench_llm,
        workbench_model=workbench_model,
    )
    try:
        return _parse_json_content(content)
    except RuntimeError:
        repair = [
            {
                "role": "system",
                "content": "只输出完整合法 JSON 对象，不要 markdown，不要解释。",
            },
            {
                "role": "user",
                "content": (
                    "上一份输出无法解析（可能截断）。请整份重写为完整 JSON。\n"
                    f"残片参考：\n{content[:1000]}"
                ),
            },
        ]
        content2 = await _complete(
            messages=repair,
            ai=ai,
            workbench_llm=workbench_llm,
            workbench_model=workbench_model,
        )
        return _parse_json_content(content2)


async def generate_with_llm(
    roles: list[str],
    *,
    ai: Optional[dict[str, Any]] = None,
    workbench_llm: Any = None,
    workbench_model: str = "",
    category: str = "hiring_insight",
    context_snippets: Optional[list[str]] = None,
    edition: Any = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    """Two-phase generation: outline (cover+titles) then rich per-card bodies."""
    cat = get_category(category)
    today = now_label()
    ai = ai or {}
    dims = [d.strip() for d in str(cat.get("llm_dims") or "").split("/") if d.strip()]
    while len(dims) < 3:
        dims.append(f"维度{len(dims) + 1}")
    dims = dims[:3]

    ctx_lines: list[str] = []
    filtered = filter_snippets(list(context_snippets or []), limit=8)
    for i, s in enumerate(filtered[:6]):
        t = re.sub(r"\s+", " ", str(s or "")).strip()
        if len(t) >= 20:
            ctx_lines.append(f"{i + 1}. {t[:160]}")
    ctx_block = (
        "参考材料（仅作市场信号；若像词典释义请忽略）：\n" + "\n".join(ctx_lines)
        if ctx_lines
        else "无可用 JD 材料，请用 AI 工程领域知识撰写，禁止编造具体公司名。"
    )
    teach = cat.get("llm_teach") or (
        "concept：是什么 + 为何重要 + 常见误解；"
        "keyPoint：【机制】【易错】【检验】各一条；"
        "example：角色→动作→可观察结果。"
    )
    anti_hollow = (
        "硬性约束：每张卡至少含 1 个具名技术/工具；【检验】必须可当场验证；"
        "example 禁止「展示一个智能客服」这类空泛句，改写为具体模块+产物；"
        "禁止「提升竞争力/核心能力/精准评估」等口号。"
    )

    # Phase 1 — short outline (rarely truncates)
    outline_msgs = [
        {
            "role": "system",
            "content": "只返回合法 JSON。字段短小完整，不要 markdown。",
        },
        {
            "role": "user",
            "content": (
                f"你是{cat['llm_role']}。今天 {today}。为「{cat['label']}」规划 3 张知识卡片大纲。\n"
                f"主题：{'、'.join(roles)}\n"
                f"三张卡片维度：{dims[0]} / {dims[1]} / {dims[2]}\n"
                f"{ctx_block}\n\n"
                f"{anti_hollow}\n"
                "输出 JSON：\n"
                '{"cover":{"title":"≤10字","description":"56-72字，写明读者将学到的具体能力",'
                '"tags":["≤6字","≤6字","≤6字"],'
                '"visual_style":"academic|warm|tech|magazine|mono 择一",'
                '"source":"可选出处≤20字","brand_signature":"可选签名≤12字"},'
                '"knowledge":['
                '{"topicTitle":"8-18字完整短语","angle":"定义型|对比型|流程型|金句型|数据型 之一",'
                '"card_kind":"quote|keypoints|compare|steps|data|concept 择一"},'
                '{"topicTitle":"8-18字完整短语","angle":"...","card_kind":"..."},'
                '{"topicTitle":"8-18字完整短语","angle":"...","card_kind":"..."}]}'
                "\n三张 topicTitle 术语不重复、禁止半截英文词；description 避免空话；三张 card_kind 尽量多样。"
            ),
        },
    ]
    outline = await _complete_json(
        messages=outline_msgs,
        ai=ai,
        workbench_llm=workbench_llm,
        workbench_model=workbench_model,
    )
    cover = outline.get("cover") if isinstance(outline.get("cover"), dict) else {}
    raw_ks = outline.get("knowledge") if isinstance(outline.get("knowledge"), list) else []
    titles: list[dict[str, str]] = []
    kind_cycle = ["concept", "keypoints", "steps", "compare", "data", "quote"]
    for i, item in enumerate(raw_ks[:3]):
        if isinstance(item, dict) and item.get("topicTitle"):
            titles.append(
                {
                    "topicTitle": clip_complete(item.get("topicTitle") or "", 36),
                    "angle": str(item.get("angle") or ["定义型", "对比型", "流程型"][i]),
                    "dim": dims[i],
                    "card_kind": str(item.get("card_kind") or kind_cycle[i]),
                }
            )
    while len(titles) < 3:
        i = len(titles)
        titles.append(
            {
                "topicTitle": dims[i][:12],
                "angle": "定义型",
                "dim": dims[i],
                "card_kind": kind_cycle[i],
            }
        )

    # Phase 2 — expand all 3 cards in one call (avoids dropping 2/3 on flaky per-card calls)
    title_lines = "\n".join(
        f"{i + 1}. 标题={meta['topicTitle']}；维度={meta['dim']}；切入={meta['angle']}；类型={meta['card_kind']}"
        for i, meta in enumerate(titles)
    )
    expand_msgs = [
        {
            "role": "system",
            "content": (
                "你是专业讲师。只返回合法 JSON："
                '{"knowledge":[...恰好3项...]}。'
                "每项必须含 topicTitle/card_kind/concept/keyPoint/example/flow；"
                "按 card_kind 补全 quote/compare/metric/source；禁止空字段与套话。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"分类：{cat['label']}；主题：{'、'.join(roles)}\n"
                f"请按下列大纲扩写 3 张完整知识卡片（标题与 card_kind 尽量沿用）：\n{title_lines}\n"
                f"{teach}\n{anti_hollow}\n{ctx_block}\n\n"
                "每项结构：\n"
                '{"topicTitle":"8-18字完整短语","card_kind":"quote|keypoints|compare|steps|data|concept",'
                '"concept":"80-110字",'
                '"keyPoint":"- 【机制】…\\n- 【易错】…\\n- 【检验】…",'
                '"example":"60-90字",'
                '"flow":["步骤1","步骤2","步骤3","步骤4"],'
                '"quote":"金句≤40字（quote 类型必填）",'
                '"source":"出处≤20字",'
                '"compare":{"left":"误区侧","right":"正确侧"},'
                '"metric":"数据短值","metric_note":"数据说明"}\n'
                "flow 为机制链路 3–4 个短词（每词≤6字），须对应【机制】中的具名组件。"
                "keyPoint 恰好 3 行，分别以【机制】【易错】【检验】开头。"
                "三张卡片术语与案例不重复。一次输出完整 JSON，不要截断。"
            ),
        },
    ]
    try:
        expanded = await _complete_json(
            messages=expand_msgs,
            ai=ai,
            workbench_llm=workbench_llm,
            workbench_model=workbench_model,
        )
    except Exception:  # noqa: BLE001
        expanded = {}

    knowledge: list[dict[str, Any]] = []
    raw_exp = expanded.get("knowledge") if isinstance(expanded.get("knowledge"), list) else []
    # Also accept top-level list mistake
    if not raw_exp and isinstance(expanded, list):
        raw_exp = expanded

    for i, meta in enumerate(titles):
        card: dict[str, Any] = {
            "topicTitle": meta["topicTitle"],
            "card_kind": meta.get("card_kind") or "concept",
        }
        if i < len(raw_exp) and isinstance(raw_exp[i], dict):
            card = {**raw_exp[i]}
            card["topicTitle"] = card.get("topicTitle") or meta["topicTitle"]
            card["card_kind"] = card.get("card_kind") or meta.get("card_kind") or "concept"
        # Retry single card if body still empty
        if len(str(card.get("concept") or "")) < 24 or not str(card.get("keyPoint") or "").strip():
            one_msgs = [
                {
                    "role": "system",
                    "content": "只返回一张卡片的 JSON 对象（不要数组）。字段齐全。",
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{meta['topicTitle']}；维度：{meta['dim']}；"
                        f"类型：{meta.get('card_kind') or 'concept'}；主题：{'、'.join(roles)}\n"
                        f"{teach}\n{anti_hollow}\n"
                        "输出：{\"topicTitle\":\"...\",\"card_kind\":\"concept\","
                        "\"concept\":\"80-110字，含具名技术\","
                        "\"keyPoint\":\"- 【机制】含组件名…\\n- 【易错】真实故障…\\n- 【检验】可验证动作…\","
                        "\"example\":\"角色→模块→产物（含数字）\",\"flow\":[\"a\",\"b\",\"c\"],"
                        "\"quote\":\"\",\"source\":\"\",\"compare\":{\"left\":\"\",\"right\":\"\"},"
                        "\"metric\":\"\",\"metric_note\":\"\"}"
                    ),
                },
            ]
            try:
                one = await _complete_json(
                    messages=one_msgs,
                    ai=ai,
                    workbench_llm=workbench_llm,
                    workbench_model=workbench_model,
                )
                if isinstance(one.get("knowledge"), list) and one["knowledge"]:
                    one = one["knowledge"][0] if isinstance(one["knowledge"][0], dict) else one
                if isinstance(one, dict) and (one.get("concept") or one.get("keyPoint")):
                    one["topicTitle"] = one.get("topicTitle") or meta["topicTitle"]
                    card = one
            except Exception:  # noqa: BLE001
                pass
        knowledge.append(card)

    parsed = {"cover": cover, "knowledge": knowledge}
    return normalize_llm_payload(
        parsed,
        roles,
        category=cat["id"],
        edition=edition,
        user_id=user_id,
        email=email,
    )


async def compose_with_llm(
    roles: list[str],
    *,
    evidence_pack: dict[str, Any],
    ai: Optional[dict[str, Any]] = None,
    workbench_llm: Any = None,
    workbench_model: str = "",
    category: str = "hiring_insight",
    edition: Any = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
) -> dict[str, Any]:
    """Evidence-aware composition: outline 5–6 cards then expand by card_kind."""
    cat = get_category(category)
    today = now_label()
    ai = ai or {}
    evid = selected_evidences(evidence_pack)
    ctx_lines = [
        f'{e["id"]} (score={e.get("score", 0)}): {str(e.get("text") or "")[:120]}'
        for e in evid[:28]
    ]
    ctx_block = (
        "证据列表（只能引用下列 id，禁止编造）：\n" + "\n".join(ctx_lines)
        if ctx_lines
        else "无可用证据；请用领域知识撰写，stance 视为 opinion，evidenceIds 可为空数组。"
    )
    teach = cat.get("llm_teach") or (
        "concept：是什么 + 为何重要；"
        "keyPoint：4–6 条要点（可选【机制】【易错】【检验】）；"
        "example：角色→动作→可观察结果。"
    )
    anti_hollow = (
        "硬性约束：每张卡至少含 1 个具名技术/工具；"
        "example 禁止「展示一个智能客服」这类空泛句，改写为具体模块+产物；"
        "禁止「提升竞争力/核心能力/精准评估」等口号；"
        "禁止编造 evidenceIds，只能使用证据列表中的 id。"
    )
    allowed_ids = ", ".join(e["id"] for e in evid[:28]) or "(无)"
    diagram_types = "flow|cycle|compare|stack|callout|bullets"

    outline_msgs = [
        {
            "role": "system",
            "content": "只返回合法 JSON。字段短小完整，不要 markdown。",
        },
        {
            "role": "user",
            "content": (
                f"你是{cat['llm_role']}。今天 {today}。为「{cat['label']}」规划 5–6 张知识卡片大纲。\n"
                f"主题：{'、'.join(roles)}\n"
                f"{ctx_block}\n\n"
                f"{anti_hollow}\n"
                "输出 JSON：\n"
                '{"cover":{"title":"8-18字完整刊名，禁止半截词","description":"56-72字，写明读者将学到的具体能力",'
                '"tags":["≤8字","≤8字","≤8字"],'
                '"visual_style":"academic|warm|tech|magazine|mono 择一",'
                '"source":"可选出处≤20字","brand_signature":"可选签名≤12字"},'
                '"frontMatter":{"guide":{"headline":"本期导读","promises":["≤28字","≤28字","≤28字"]}},'
                '"knowledge":['
                '{"topicTitle":"8-18字完整短语（禁止「定义State」这类半截标题）","angle":"定义型|对比型|流程型|金句型|数据型 之一",'
                '"card_kind":"quote|keypoints|compare|steps|data|concept 择一",'
                f'"diagram":{{"type":"{diagram_types}"}},'
                '"evidenceIds":["e1"]},'
                "... 共 5 到 6 项 ...]}"
                f"\n可用 evidenceIds：{allowed_ids}；每张卡至少 1 个（若列表为空则传 []）。"
                "\ntopicTitle 必须是完整可独立理解的短语（8-18字），禁止截断英文专有名词；"
                "description 避免空话；"
                "目标 5–6 张；至少 3 种 card_kind；禁止清一色 flow；"
                "每卡必须给 diagram.type；frontMatter.guide.promises 恰好 3 条且每条≤28字。"
            ),
        },
    ]
    outline = await _complete_json(
        messages=outline_msgs,
        ai=ai,
        workbench_llm=workbench_llm,
        workbench_model=workbench_model,
    )
    cover = outline.get("cover") if isinstance(outline.get("cover"), dict) else {}
    front_matter = (
        outline.get("frontMatter") if isinstance(outline.get("frontMatter"), dict) else {}
    )
    raw_ks = outline.get("knowledge") if isinstance(outline.get("knowledge"), list) else []
    titles: list[dict[str, Any]] = []
    kind_cycle = ["concept", "keypoints", "steps", "compare", "data", "quote"]
    diagram_cycle = ["bullets", "stack", "flow", "compare", "callout", "cycle"]
    for i, item in enumerate(raw_ks[:6]):
        if isinstance(item, dict) and item.get("topicTitle"):
            eids = item.get("evidenceIds") if isinstance(item.get("evidenceIds"), list) else []
            diagram = item.get("diagram") if isinstance(item.get("diagram"), dict) else {}
            titles.append(
                {
                    "topicTitle": clip_complete(item.get("topicTitle") or "", 36),
                    "angle": str(item.get("angle") or "定义型"),
                    "card_kind": str(item.get("card_kind") or kind_cycle[i % len(kind_cycle)]),
                    "diagram": diagram,
                    "evidenceIds": [str(x) for x in eids if str(x).strip()][:4],
                }
            )
    while len(titles) < 5:
        i = len(titles)
        fallback_eid = [evid[0]["id"]] if evid else []
        titles.append(
            {
                "topicTitle": f"要点{i + 1}",
                "angle": "定义型",
                "card_kind": kind_cycle[i % len(kind_cycle)],
                "diagram": {"type": diagram_cycle[i % len(diagram_cycle)]},
                "evidenceIds": fallback_eid,
            }
        )

    title_lines = "\n".join(
        f"{i + 1}. 标题={meta['topicTitle']}；切入={meta['angle']}；"
        f"类型={meta['card_kind']}；diagram={meta.get('diagram') or {}}；"
        f"evidenceIds={meta.get('evidenceIds') or []}"
        for i, meta in enumerate(titles)
    )
    n = len(titles)
    expand_msgs = [
        {
            "role": "system",
            "content": (
                "你是专业讲师。只返回合法 JSON："
                f'{{"knowledge":[...恰好{n}项...]}}。'
                "每项必须含 topicTitle/card_kind/concept/keyPoint/example/diagram/evidenceIds；"
                "按 card_kind 灵活补全 quote/compare/metric/flow/source；禁止空字段与套话；"
                "禁止强制【机制】【易错】【检验】三行格式。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"分类：{cat['label']}；主题：{'、'.join(roles)}\n"
                f"请按下列大纲扩写 {n} 张完整知识卡片（标题与 card_kind、diagram、evidenceIds 尽量沿用）：\n"
                f"{title_lines}\n"
                f"{teach}\n{anti_hollow}\n{ctx_block}\n\n"
                "每项结构：\n"
                '{"topicTitle":"8-18字完整短语","card_kind":"quote|keypoints|compare|steps|data|concept",'
                '"concept":"140-260字",'
                '"keyPoint":"- 要点1\\n- 要点2\\n- 要点3\\n- 要点4",'
                '"example":"90-140字",'
                f'"diagram":{{"type":"{diagram_types}",'
                '"nodes":[{"label":"≤10字"},{"label":"≤10字"},{"label":"≤10字"}]}},'
                '"flow":["4-12字完整步骤，如定义StateGraph，禁止半截词"],'
                '"quote":"金句≤40字（quote 类型必填）",'
                '"source":"出处≤20字",'
                '"compare":{"left":"误区侧","right":"正确侧"},'
                '"metric":"数据短值","metric_note":"数据说明",'
                f'"evidenceIds":["从 {allowed_ids} 选用"]}}\n'
                "concept 140–260字；keyPoint 4–6 条；example 90–160字；"
                "补全 diagram.nodes（完整短标签，禁止「定义State…」）；steps→flow/cycle；compare 双侧；"
                "data 补 metric；quote 补金句；禁止清一色 flow。"
                f"{n} 张卡片术语与案例不重复。一次输出完整 JSON，不要截断。"
            ),
        },
    ]
    try:
        expanded = await _complete_json(
            messages=expand_msgs,
            ai=ai,
            workbench_llm=workbench_llm,
            workbench_model=workbench_model,
        )
    except Exception:  # noqa: BLE001
        expanded = {}

    knowledge: list[dict[str, Any]] = []
    raw_exp = expanded.get("knowledge") if isinstance(expanded.get("knowledge"), list) else []
    if not raw_exp and isinstance(expanded, list):
        raw_exp = expanded

    for i, meta in enumerate(titles):
        card: dict[str, Any] = {
            "topicTitle": meta["topicTitle"],
            "card_kind": meta.get("card_kind") or "concept",
            "diagram": meta.get("diagram") or {},
            "evidenceIds": list(meta.get("evidenceIds") or []),
        }
        if i < len(raw_exp) and isinstance(raw_exp[i], dict):
            card = {**raw_exp[i]}
            card["topicTitle"] = card.get("topicTitle") or meta["topicTitle"]
            card["card_kind"] = card.get("card_kind") or meta.get("card_kind") or "concept"
            if not isinstance(card.get("diagram"), dict) or not card.get("diagram"):
                card["diagram"] = meta.get("diagram") or {}
            if not isinstance(card.get("evidenceIds"), list) or not card.get("evidenceIds"):
                card["evidenceIds"] = list(meta.get("evidenceIds") or [])
        if len(str(card.get("concept") or "")) < 24 or not str(card.get("keyPoint") or "").strip():
            one_msgs = [
                {
                    "role": "system",
                    "content": "只返回一张卡片的 JSON 对象（不要数组）。字段齐全。",
                },
                {
                    "role": "user",
                    "content": (
                        f"标题：{meta['topicTitle']}；"
                        f"类型：{meta.get('card_kind') or 'concept'}；主题：{'、'.join(roles)}\n"
                        f"evidenceIds 必须从 [{allowed_ids}] 选用："
                        f"{meta.get('evidenceIds') or []}\n"
                        f"{teach}\n{anti_hollow}\n"
                        "输出：{\"topicTitle\":\"...\",\"card_kind\":\"concept\","
                        "\"concept\":\"140-220字，含具名技术\","
                        "\"keyPoint\":\"- 要点1\\n- 要点2\\n- 要点3\\n- 要点4\","
                        "\"example\":\"角色→模块→产物（含数字）90-140字\","
                        f"\"diagram\":{{\"type\":\"{diagram_types}\","
                        "\"nodes\":[{\"label\":\"a\"},{\"label\":\"b\"},{\"label\":\"c\"}]}},"
                        "\"flow\":[\"a\",\"b\",\"c\"],"
                        "\"quote\":\"\",\"source\":\"\",\"compare\":{\"left\":\"\",\"right\":\"\"},"
                        "\"metric\":\"\",\"metric_note\":\"\",\"evidenceIds\":[]}"
                    ),
                },
            ]
            try:
                one = await _complete_json(
                    messages=one_msgs,
                    ai=ai,
                    workbench_llm=workbench_llm,
                    workbench_model=workbench_model,
                )
                if isinstance(one.get("knowledge"), list) and one["knowledge"]:
                    one = one["knowledge"][0] if isinstance(one["knowledge"][0], dict) else one
                if isinstance(one, dict) and (one.get("concept") or one.get("keyPoint")):
                    one["topicTitle"] = one.get("topicTitle") or meta["topicTitle"]
                    if not isinstance(one.get("diagram"), dict) or not one.get("diagram"):
                        one["diagram"] = meta.get("diagram") or {}
                    if not isinstance(one.get("evidenceIds"), list) or not one.get("evidenceIds"):
                        one["evidenceIds"] = list(meta.get("evidenceIds") or [])
                    card = one
            except Exception:  # noqa: BLE001
                pass
        knowledge.append(card)

    parsed = {"cover": cover, "frontMatter": front_matter, "knowledge": knowledge}
    return normalize_llm_payload(
        parsed,
        roles,
        category=cat["id"],
        edition=edition,
        user_id=user_id,
        email=email,
        evidence_pack=evidence_pack,
        rich_journal=True,
    )
