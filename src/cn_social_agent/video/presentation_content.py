"""LLM draft + depth validation for web presentation content.json."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

_MAX_TOKENS = 8192
_TEMPERATURE = 0.4

# Shallow / empty nutrition patterns we reject or flag
_SHALLOW_RE = re.compile(
    r"(今天讲一下|简单介绍|众所周知|赋能|抓住机遇|未来可期|干货满满|一文读懂)",
    re.I,
)

# 实测讲解弧线（对齐产品实测讲解片：Hook→差异→概念→安装→实测→意外→进阶→收束）
_ARC_ROLES = (
    "hook",
    "differentiate",
    "concept",
    "setup",
    "demo",
    "discovery",
    "advanced",
    "wrap",
)
_REQUIRED_ARC = frozenset({"hook", "differentiate", "concept", "setup", "demo", "wrap"})
_CTA_RE = re.compile(r"(本周|立刻|下一步|自己试|动手|仓库|安装|复现|行动)")

PRESENTATION_DRAFT_SYSTEM = """你是资深「产品实测讲解」编剧 + 信息架构师。
任务：把主题打磨成可 OBS 录屏的网页演示文稿——叙事像真机实测片，不是空洞图示课。

对标结构（章节 role 必须齐全，顺序大致如下）：
1. hook — 为何值得看：爆点/趋势/痛点，30 秒内立住好奇
2. differentiate — 与旧做法/竞品的可检验差异（必须有 compare 图）
3. concept — 核心机制命名+一句话说清（禁止只堆名词）
4. setup — 安装/前置/怎么跑起来（checklist 或 pipeline）
5. demo — 第一次真实验证：操作→可观察结果→你要观众看什么
6. discovery — 意外发现/反直觉点（增强可信度；可与 demo 合并页但 role 仍标 discovery）
7. advanced — 进阶：并行/长期目标/多 Agent 等（可与 demo 二选一加深，建议有）
8. wrap — 记住一句话 + 本周可执行行动（CTA）

硬性质量条（不满足则重写直到满足）：
1. thesis：一句可反驳主张（差异点，不是标题复述）
2. outline：6–8 行，对应上述弧线时间戳式章节
3. full_script：≥350 汉字，按章分段；有停顿点；结尾必须有可执行 CTA
4. chapters：≥6 章；每章必填 role（上列枚举）；全片 slides≥18；diagram≥8
5. demo/discovery/advanced 章的 slides 须含 outcome（观众应看到的可观察结果，≤48字）
   且 demo 章至少一页须带 verify：{command, expected}——可在沙箱复现的命令+预期输出片段（不许吹嘘）
6. 每轴/论点：机制 + 易错 + 检验（或追问）至少覆盖其一
7. diagram.type 仅限：axes3 | pipeline | state | cards | compare | checklist
8. 文案具体（对象/条件/数字）；禁止赋能/干货/一文读懂等套话
9. 若有 research_notes，必须吸收事实并带来源感（不必写 URL）

输出严格 JSON（不要 markdown 围栏）：
{
  "title": "≤18字",
  "theme": "talent-map|paper-press|desk|terminal-green",
  "thesis": "一句主张",
  "audience": "受众",
  "outline": "多行大纲（带大致节拍，如 0:00 为何值得看）",
  "full_script": "口播全文",
  "chapters": [
    {
      "title": "章名",
      "role": "hook|differentiate|concept|setup|demo|discovery|advanced|wrap",
      "slides": [
        {
          "eyebrow": "可选",
          "title": "≤18字",
          "body": "可选，具体",
          "narration": "本步口播（建议每步必填；demo 步必填）",
          "duration_ms": 0,
          "outcome": "可观察结果（demo/discovery/advanced 建议必填）",
          "points": ["可选"],
          "flow": ["可选"],
          "accent_title": false,
          "verify": { "command": "可复现命令（demo 步必填）", "expected": "预期输出片段(子串)或 re:正则", "image": "可选docker镜像", "network": "none|bridge" },
          "diagram": { "type": "compare|pipeline|state|cards|checklist|axes3", "...": "按类型填" }
        }
      ]
    }
  ]
}

diagram 形状：
- axes3: { "type":"axes3", "items":[{"k","t","d"},×3] }
- pipeline: { "type":"pipeline", "items":["…"] }
- state: { "type":"state", "nodes":["…"], "loops":["…"] }
- cards: { "type":"cards", "cols":1|3, "items":[{"k","t","d"}] }
- compare: { "type":"compare", "left":{"k","t","d"}, "right":{"k","t","d"} }
- checklist: { "type":"checklist", "items":["…"] }
"""


def _strip_fence(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```(?:json|JSON)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def _clip(s: Any, n: int) -> str:
    t = str(s or "").replace("\r\n", "\n").strip()
    if len(t) <= n:
        return t
    return t[: max(0, n - 1)].rstrip("，。、；;,. ") + "…"


def count_slides(chapters: list[dict[str, Any]]) -> int:
    return sum(len(c.get("slides") or []) for c in chapters or [])


def count_diagrams(chapters: list[dict[str, Any]]) -> int:
    n = 0
    for c in chapters or []:
        for s in c.get("slides") or []:
            if isinstance(s, dict) and isinstance(s.get("diagram"), dict) and s["diagram"].get("type"):
                n += 1
    return n


def _chapter_roles(chapters: list[dict[str, Any]]) -> set[str]:
    roles: set[str] = set()
    for c in chapters or []:
        if not isinstance(c, dict):
            continue
        role = str(c.get("role") or "").strip().lower()
        if role in _ARC_ROLES:
            roles.add(role)
    return roles


def _demo_outcomes_ok(chapters: list[dict[str, Any]]) -> bool:
    """demo/discovery/advanced chapters need at least one slide with outcome."""
    need = {"demo", "discovery", "advanced"}
    found_roles = set()
    for c in chapters or []:
        if not isinstance(c, dict):
            continue
        role = str(c.get("role") or "").strip().lower()
        if role not in need:
            continue
        for s in c.get("slides") or []:
            if isinstance(s, dict) and str(s.get("outcome") or "").strip():
                found_roles.add(role)
                break
    # Only require outcomes for roles that are present; demo is required by arc
    present = _chapter_roles(chapters) & need
    if not present:
        return False
    return present <= found_roles


def _has_compare_diagram(chapters: list[dict[str, Any]]) -> bool:
    for c in chapters or []:
        for s in (c.get("slides") or []) if isinstance(c, dict) else []:
            if not isinstance(s, dict):
                continue
            d = s.get("diagram")
            if isinstance(d, dict) and d.get("type") == "compare":
                return True
    return False


_VERIFY_ROLES = {"demo", "discovery", "advanced"}


def _slide_has_verify_decl(slide: dict[str, Any]) -> bool:
    v = slide.get("verify")
    if not isinstance(v, dict):
        return False
    return bool(str(v.get("command") or "").strip()) and bool(
        str(v.get("expected") or "").strip()
    )


def _demo_verify_declared(chapters: list[dict[str, Any]]) -> bool:
    """demo 章（及在场的 discovery/advanced 章）须至少声明一条 verify(command+expected)。

    这是内容期「不许吹嘘」门禁：没有可复现命令+预期，就不算达标。
    """
    present: set[str] = set()
    declared: set[str] = set()
    for c in chapters or []:
        if not isinstance(c, dict):
            continue
        role = str(c.get("role") or "").strip().lower()
        if role not in _VERIFY_ROLES:
            continue
        present.add(role)
        for s in c.get("slides") or []:
            if isinstance(s, dict) and _slide_has_verify_decl(s):
                declared.add(role)
                break
    if "demo" not in present:
        return False
    return present <= declared


def _narration_coverage(chapters: list[dict[str, Any]]) -> tuple[int, int]:
    total = 0
    with_n = 0
    for c in chapters or []:
        if not isinstance(c, dict):
            continue
        for s in c.get("slides") or []:
            if not isinstance(s, dict):
                continue
            total += 1
            if str(s.get("narration") or s.get("body") or "").strip():
                with_n += 1
    return with_n, total


def depth_report(doc: dict[str, Any]) -> dict[str, Any]:
    """Return pass/fail metrics for presentation richness (实测讲解弧线)."""
    chapters = doc.get("chapters") if isinstance(doc.get("chapters"), list) else []
    script = str(doc.get("full_script") or "")
    thesis = str(doc.get("thesis") or "")
    slides = count_slides(chapters)
    diagrams = count_diagrams(chapters)
    shallow_hits = _SHALLOW_RE.findall(script + "\n" + thesis + "\n" + str(doc.get("title") or ""))
    roles = _chapter_roles(chapters)
    missing_arc = sorted(_REQUIRED_ARC - roles)
    narr_n, narr_total = _narration_coverage(chapters)
    checks = {
        "chapters_ge_6": len(chapters) >= 6,
        "slides_ge_18": slides >= 18,
        "diagrams_ge_8": diagrams >= 8,
        "script_ge_350": len(re.sub(r"\s+", "", script)) >= 350,
        "has_thesis": len(thesis.strip()) >= 8,
        "no_shallow_cliche": len(shallow_hits) == 0,
        "arc_roles_complete": len(missing_arc) == 0,
        "has_compare_diagram": _has_compare_diagram(chapters),
        "demo_has_outcome": _demo_outcomes_ok(chapters),
        "demo_verify_declared": _demo_verify_declared(chapters),
        "script_has_cta": bool(_CTA_RE.search(script)),
        "narration_coverage_ge_half": narr_total == 0
        or narr_n >= max(1, narr_total // 2),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "stats": {
            "chapters": len(chapters),
            "slides": slides,
            "diagrams": diagrams,
            "script_chars": len(re.sub(r"\s+", "", script)),
            "shallow_hits": shallow_hits[:5],
            "roles": sorted(roles),
            "missing_arc": missing_arc,
            "narration_slides": narr_n,
        },
    }


def _norm_verify_block(raw: Any) -> Optional[dict[str, Any]]:
    """Preserve/normalize a slide verify block (lazy import to stay leaf)."""
    from cn_social_agent.video.verification import normalize_verify

    return normalize_verify(raw)


def _norm_diagram(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    t = str(raw.get("type") or "").strip()
    if t not in ("axes3", "pipeline", "state", "cards", "compare", "checklist"):
        return None
    if t == "axes3":
        items = raw.get("items") if isinstance(raw.get("items"), list) else []
        clean = []
        for it in items[:3]:
            if not isinstance(it, dict):
                continue
            clean.append(
                {
                    "k": _clip(it.get("k"), 8),
                    "t": _clip(it.get("t"), 12),
                    "d": _clip(it.get("d"), 24),
                }
            )
        while len(clean) < 3:
            clean.append({"k": "", "t": "—", "d": ""})
        return {"type": "axes3", "items": clean}
    if t == "pipeline":
        items = [ _clip(x, 12) for x in (raw.get("items") or []) if str(x).strip()][:6]
        return {"type": "pipeline", "items": items or ["步骤"]}
    if t == "state":
        nodes = [ _clip(x, 10) for x in (raw.get("nodes") or []) if str(x).strip()][:4]
        loops = [ _clip(x, 28) for x in (raw.get("loops") or []) if str(x).strip()][:2]
        return {"type": "state", "nodes": nodes or ["A", "B"], "loops": loops}
    if t == "cards":
        items = []
        for it in (raw.get("items") or [])[:6]:
            if not isinstance(it, dict):
                continue
            items.append(
                {
                    "k": _clip(it.get("k"), 10),
                    "t": _clip(it.get("t"), 18),
                    "d": _clip(it.get("d"), 48),
                }
            )
        cols = raw.get("cols")
        try:
            cols_i = int(cols) if cols is not None else 1
        except (TypeError, ValueError):
            cols_i = 1
        if cols_i not in (1, 2, 3):
            cols_i = 1
        return {"type": "cards", "cols": cols_i, "items": items or [{"t": "要点", "d": ""}]}
    if t == "compare":
        left = raw.get("left") if isinstance(raw.get("left"), dict) else {}
        right = raw.get("right") if isinstance(raw.get("right"), dict) else {}
        def side(d: dict) -> dict:
            return {
                "k": _clip(d.get("k"), 10),
                "t": _clip(d.get("t"), 18),
                "d": _clip(d.get("d"), 56),
            }
        return {"type": "compare", "left": side(left), "right": side(right)}
    items = [ _clip(x, 36) for x in (raw.get("items") or []) if str(x).strip()][:6]
    return {"type": "checklist", "items": items or ["检查项"]}


def normalize_presentation_doc(raw: dict[str, Any], *, topic: str = "") -> dict[str, Any]:
    chapters_in = raw.get("chapters") if isinstance(raw.get("chapters"), list) else []
    chapters: list[dict[str, Any]] = []
    for ch in chapters_in[:10]:
        if not isinstance(ch, dict):
            continue
        slides_out = []
        for sl in (ch.get("slides") or [])[:8]:
            if not isinstance(sl, dict):
                continue
            item: dict[str, Any] = {
                "title": _clip(sl.get("title") or "未命名", 22),
            }
            if sl.get("eyebrow"):
                item["eyebrow"] = _clip(sl.get("eyebrow"), 24)
            if sl.get("body"):
                item["body"] = _clip(sl.get("body"), 120)
            if sl.get("narration"):
                item["narration"] = _clip(sl.get("narration"), 200)
            elif sl.get("body"):
                # Seed narration from body when LLM omitted it — timeline needs text
                item["narration"] = _clip(sl.get("body"), 200)
            if sl.get("outcome"):
                item["outcome"] = _clip(sl.get("outcome"), 48)
            verify = _norm_verify_block(sl.get("verify"))
            if verify:
                item["verify"] = verify
            narr_text = str(item.get("narration") or "")
            try:
                dur = int(sl.get("duration_ms") or 0)
            except (TypeError, ValueError):
                dur = 0
            if dur <= 0 and narr_text:
                # ~120ms/字，与舞台无音频回退一致
                dur = max(2200, len(narr_text.strip()) * 120)
            if dur > 0:
                item["duration_ms"] = min(dur, 60000)
            if sl.get("accent_title"):
                item["accent_title"] = True
            pts = sl.get("points")
            if isinstance(pts, list) and pts:
                item["points"] = [_clip(p, 48) for p in pts if str(p).strip()][:5]
            flow = sl.get("flow")
            if isinstance(flow, list) and flow:
                item["flow"] = [_clip(f, 12) for f in flow if str(f).strip()][:6]
            diag = _norm_diagram(sl.get("diagram"))
            if diag:
                item["diagram"] = diag
            slides_out.append(item)
        if slides_out:
            ch_out: dict[str, Any] = {
                "title": _clip(ch.get("title") or "章节", 24),
                "slides": slides_out,
            }
            role = str(ch.get("role") or "").strip().lower()
            if role in _ARC_ROLES:
                ch_out["role"] = role
            chapters.append(ch_out)

    theme = str(raw.get("theme") or "talent-map").strip() or "talent-map"
    if theme not in ("talent-map", "paper-press", "desk", "terminal-green"):
        theme = "talent-map"

    return {
        "title": _clip(raw.get("title") or topic or "讲解演示", 24),
        "theme": theme,
        "thesis": _clip(raw.get("thesis"), 80),
        "audience": _clip(raw.get("audience"), 40),
        "outline": str(raw.get("outline") or "").strip(),
        "full_script": str(raw.get("full_script") or "").strip(),
        "chapters": chapters,
    }


def build_user_prompt(
    *,
    topic: str,
    research_notes: str = "",
    audience: str = "",
    angle: str = "",
    aspect: str = "9:16",
    theme: str = "talent-map",
) -> str:
    parts = [
        f"主题：{topic}",
        f"画幅：{aspect}",
        f"建议主题色：{theme}",
    ]
    if audience:
        parts.append(f"受众：{audience}")
    if angle:
        parts.append(f"切入角度：{angle}")
    if research_notes.strip():
        parts.append("调研摘录（必须吸收，禁止无视）：\n" + research_notes.strip()[:4000])
    parts.append(
        "请按实测讲解弧线内部完成：①为何值得看 ②可检验差异 ③核心机制 "
        "④怎么跑起来 ⑤第一次真实验证+可观察结果 ⑥意外发现 ⑦进阶 ⑧本周行动；"
        "每章标注 role；demo 步写 outcome。不要输出思考过程，只输出 JSON。"
    )
    return "\n".join(parts)


async def generate_presentation_content(
    llm: Any,
    *,
    topic: str,
    research_notes: str = "",
    audience: str = "",
    angle: str = "",
    aspect: str = "9:16",
    theme: str = "talent-map",
    model: str = "",
    repair: bool = True,
) -> dict[str, Any]:
    """Call workbench LLM and return normalized doc + depth report."""
    messages = [
        {"role": "system", "content": PRESENTATION_DRAFT_SYSTEM},
        {
            "role": "user",
            "content": build_user_prompt(
                topic=topic,
                research_notes=research_notes,
                audience=audience,
                angle=angle,
                aspect=aspect,
                theme=theme,
            ),
        },
    ]
    data = await llm.chat_completion(
        messages,
        model=model or "",
        max_tokens=_MAX_TOKENS,
        temperature=_TEMPERATURE,
    )
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError("LLM 返回空内容")
    raw_text = _strip_fence(str(content))
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # try extract object
        m = re.search(r"\{[\s\S]*\}", raw_text)
        if not m:
            raise RuntimeError("LLM 未返回合法 JSON")
        parsed = json.loads(m.group(0))
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM JSON 根节点必须是对象")

    doc = normalize_presentation_doc(parsed, topic=topic)
    report = depth_report(doc)

    if repair and not report["ok"]:
        fix_messages = messages + [
            {"role": "assistant", "content": raw_text},
            {
                "role": "user",
                "content": (
                    "未达标，请按下列失败项重写完整 JSON（不要解释）：\n"
                    + json.dumps(report, ensure_ascii=False)
                    + "\n要求：章节≥6且 role 覆盖 hook/differentiate/concept/setup/demo/wrap；"
                    "slides≥18、diagram≥8、至少一页 compare；demo 类章有 outcome；"
                    "口播≥350字且含 CTA；必须有 thesis；去掉空洞套话。"
                ),
            },
        ]
        data2 = await llm.chat_completion(
            fix_messages,
            model=model or "",
            max_tokens=_MAX_TOKENS,
            temperature=0.35,
        )
        content2 = ((data2.get("choices") or [{}])[0].get("message") or {}).get("content")
        if content2:
            raw2 = _strip_fence(str(content2))
            try:
                parsed2 = json.loads(raw2)
            except json.JSONDecodeError:
                m2 = re.search(r"\{[\s\S]*\}", raw2)
                parsed2 = json.loads(m2.group(0)) if m2 else None
            if isinstance(parsed2, dict):
                doc = normalize_presentation_doc(parsed2, topic=topic)
                report = depth_report(doc)

    return {"ok": report["ok"], "content": doc, "depth": report}
