"""Deterministic canvas starter templates."""

from __future__ import annotations

from typing import Any

from cn_social_agent.content.canvas import new_edge_id, new_node_id, normalize_canvas

TEMPLATES: tuple[dict[str, str], ...] = (
    {"id": "blank", "label": "空白画布"},
    {"id": "topic_funnel", "label": "选题漏斗"},
    {"id": "script_structure", "label": "脚本结构"},
    {"id": "swot", "label": "SWOT 分析"},
)


def list_canvas_templates() -> list[dict[str, str]]:
    return [dict(t) for t in TEMPLATES]


def _node(
    nid: str,
    *,
    kind: str,
    title: str,
    text: str = "",
    x: int,
    y: int,
    color: str = "",
) -> dict[str, Any]:
    return {
        "id": nid,
        "kind": kind,
        "title": title,
        "text": text,
        "x": x,
        "y": y,
        "color": color,
    }


def _edge(eid: str, frm: str, to: str, label: str = "") -> dict[str, Any]:
    return {"id": eid, "from": frm, "to": to, "label": label}


def _topic_funnel() -> dict[str, Any]:
    nodes = [
        _node(
            "tpl_tf_audience",
            kind="question",
            title="受众痛点",
            text="谁在什么场景下最难受？",
            x=40,
            y=80,
            color="pink",
        ),
        _node(
            "tpl_tf_angle",
            kind="outline",
            title="选题角度",
            text="用一句话写出差异化切入点",
            x=360,
            y=80,
            color="blue",
        ),
        _node(
            "tpl_tf_hook",
            kind="hook",
            title="开场钩子",
            text="前 3 秒要抓住什么情绪？",
            x=680,
            y=80,
            color="yellow",
        ),
        _node(
            "tpl_tf_proof",
            kind="evidence",
            title="证据 / 案例",
            text="可引用的数据、截图或故事",
            x=360,
            y=280,
            color="green",
        ),
        _node(
            "tpl_tf_cta",
            kind="note",
            title="行动号召",
            text="希望观众做什么？关注 / 评论 / 试用",
            x=680,
            y=280,
        ),
    ]
    edges = [
        _edge("tpl_tf_e1", "tpl_tf_audience", "tpl_tf_angle", "提炼"),
        _edge("tpl_tf_e2", "tpl_tf_angle", "tpl_tf_hook", "包装"),
        _edge("tpl_tf_e3", "tpl_tf_angle", "tpl_tf_proof", "支撑"),
        _edge("tpl_tf_e4", "tpl_tf_hook", "tpl_tf_cta", "收束"),
    ]
    return {"nodes": nodes, "edges": edges, "title": "选题漏斗"}


def _script_structure() -> dict[str, Any]:
    nodes = [
        _node(
            "tpl_ss_hook",
            kind="hook",
            title="钩子",
            text="冲突 / 反常识 / 提问",
            x=40,
            y=120,
            color="yellow",
        ),
        _node(
            "tpl_ss_setup",
            kind="outline",
            title="铺垫",
            text="背景与问题定义",
            x=320,
            y=120,
            color="blue",
        ),
        _node(
            "tpl_ss_body",
            kind="note",
            title="干货主体",
            text="3 个要点，每点一例",
            x=600,
            y=120,
            color="green",
        ),
        _node(
            "tpl_ss_twist",
            kind="question",
            title="转折",
            text="常见误区或意外对比",
            x=880,
            y=120,
            color="pink",
        ),
        _node(
            "tpl_ss_cta",
            kind="outline",
            title="结尾 CTA",
            text="总结 + 下一步行动",
            x=1160,
            y=120,
        ),
    ]
    edges = [
        _edge("tpl_ss_e1", "tpl_ss_hook", "tpl_ss_setup", "然后"),
        _edge("tpl_ss_e2", "tpl_ss_setup", "tpl_ss_body", "展开"),
        _edge("tpl_ss_e3", "tpl_ss_body", "tpl_ss_twist", "反转"),
        _edge("tpl_ss_e4", "tpl_ss_twist", "tpl_ss_cta", "收束"),
    ]
    return {"nodes": nodes, "edges": edges, "title": "脚本结构"}


def _swot() -> dict[str, Any]:
    nodes = [
        _node(
            "tpl_sw_s",
            kind="note",
            title="优势 Strengths",
            text="内部可控的强项",
            x=40,
            y=80,
            color="green",
        ),
        _node(
            "tpl_sw_w",
            kind="note",
            title="劣势 Weaknesses",
            text="内部短板与约束",
            x=360,
            y=80,
            color="pink",
        ),
        _node(
            "tpl_sw_o",
            kind="outline",
            title="机会 Opportunities",
            text="外部可借势的窗口",
            x=40,
            y=300,
            color="blue",
        ),
        _node(
            "tpl_sw_t",
            kind="question",
            title="威胁 Threats",
            text="外部风险与竞争",
            x=360,
            y=300,
            color="yellow",
        ),
        _node(
            "tpl_sw_insight",
            kind="hook",
            title="洞察结论",
            text="SO / WO / ST / WT 里最值得做的一件事",
            x=680,
            y=190,
            color="purple",
        ),
    ]
    edges = [
        _edge("tpl_sw_e1", "tpl_sw_s", "tpl_sw_insight", "SO"),
        _edge("tpl_sw_e2", "tpl_sw_w", "tpl_sw_insight", "WO"),
        _edge("tpl_sw_e3", "tpl_sw_o", "tpl_sw_insight", "借势"),
        _edge("tpl_sw_e4", "tpl_sw_t", "tpl_sw_insight", "避险"),
    ]
    return {"nodes": nodes, "edges": edges, "title": "SWOT 分析"}


_BUILDERS = {
    "blank": lambda: {"nodes": [], "edges": [], "title": ""},
    "topic_funnel": _topic_funnel,
    "script_structure": _script_structure,
    "swot": _swot,
}


def _with_fresh_ids(raw: dict[str, Any]) -> dict[str, Any]:
    """Same structure and layout every time, but ids unique per instantiation."""
    id_map = {n["id"]: new_node_id() for n in raw["nodes"]}
    nodes = [{**n, "id": id_map[n["id"]]} for n in raw["nodes"]]
    edges = [
        {
            **e,
            "id": new_edge_id(),
            "from": id_map[e["from"]],
            "to": id_map[e["to"]],
        }
        for e in raw["edges"]
    ]
    return {**raw, "nodes": nodes, "edges": edges}


def instantiate_canvas_template(template_id: str) -> dict[str, Any]:
    tid = str(template_id or "").strip().lower()
    builder = _BUILDERS.get(tid)
    if builder is None:
        raise ValueError(f"unknown canvas template: {template_id}")
    return normalize_canvas(_with_fresh_ids(builder()))
