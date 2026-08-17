"""Tests for presentation content depth bars (实测讲解弧线)."""

from __future__ import annotations

from cn_social_agent.video.presentation_content import (
    depth_report,
    normalize_presentation_doc,
)

_ROLES = (
    "hook",
    "differentiate",
    "concept",
    "setup",
    "demo",
    "wrap",
)


def _rich_doc():
    chapters = []
    for i, role in enumerate(_ROLES):
        slides = []
        for j in range(3):
            sl = {"title": f"章{i+1}-步{j+1}", "body": "具体机制说明，避免空话。"}
            if role in ("demo", "discovery", "advanced") and j == 0:
                sl["outcome"] = "终端出现可复现的成功日志一行"
                sl["narration"] = "我们跑完这一步，看终端是否打出成功日志。"
                sl["verify"] = {
                    "command": "python -c \"print('SUCCESS')\"",
                    "expected": "SUCCESS",
                }
            if j == 0:
                sl["diagram"] = {
                    "type": "compare",
                    "left": {"k": "误区", "t": "名词堆叠", "d": "说得出框架做不出闭环"},
                    "right": {"k": "检验", "t": "可复现", "d": "状态机+指标"},
                }
            elif j == 1:
                sl["diagram"] = {"type": "pipeline", "items": ["A", "B", "C", "D"]}
            else:
                sl["points"] = ["易错：无超时", "检验：复现一次回退"]
            slides.append(sl)
        chapters.append({"title": f"章节{i+1}", "role": role, "slides": slides})
    # extra diagrams to hit 8
    chapters[0]["slides"].append(
        {"title": "总览", "diagram": {"type": "axes3", "items": [{"t": "a"}, {"t": "b"}, {"t": "c"}]}}
    )
    chapters[1]["slides"].append(
        {"title": "清单", "diagram": {"type": "checklist", "items": ["问机制", "问易错", "问检验"]}}
    )
    script = ("甲" * 340) + "本周自己试一次安装并复现第一条日志。"
    return {
        "title": "测试稿",
        "thesis": "招聘要看可验证交付，而不是工具名词。",
        "outline": "\n".join(f"{i+1} 章" for i in range(6)),
        "full_script": script,
        "chapters": chapters,
    }


def test_depth_report_passes_rich_doc():
    doc = normalize_presentation_doc(_rich_doc())
    report = depth_report(doc)
    assert report["stats"]["slides"] >= 18
    assert report["stats"]["diagrams"] >= 8
    assert report["checks"]["arc_roles_complete"] is True
    assert report["checks"]["demo_has_outcome"] is True
    assert report["checks"]["script_has_cta"] is True
    assert report["ok"] is True


def test_depth_report_fails_shallow():
    doc = normalize_presentation_doc(
        {
            "title": "今天简单讲一下 AI",
            "thesis": "",
            "full_script": "干货满满，赋能未来。",
            "chapters": [{"title": "开场", "slides": [{"title": "你好"}]}],
        }
    )
    report = depth_report(doc)
    assert report["ok"] is False
    assert report["checks"]["slides_ge_18"] is False
    assert report["checks"]["has_thesis"] is False
    assert report["checks"]["arc_roles_complete"] is False


def test_depth_report_fails_without_demo_outcome():
    raw = _rich_doc()
    for ch in raw["chapters"]:
        if ch["role"] == "demo":
            for sl in ch["slides"]:
                sl.pop("outcome", None)
    doc = normalize_presentation_doc(raw)
    report = depth_report(doc)
    assert report["checks"]["demo_has_outcome"] is False
    assert report["ok"] is False


def test_depth_report_fails_without_demo_verify():
    raw = _rich_doc()
    for ch in raw["chapters"]:
        if ch["role"] == "demo":
            for sl in ch["slides"]:
                sl.pop("verify", None)
    doc = normalize_presentation_doc(raw)
    report = depth_report(doc)
    assert report["checks"]["demo_verify_declared"] is False
    assert report["ok"] is False


def test_normalize_preserves_verify_block():
    doc = normalize_presentation_doc(
        {
            "title": "t",
            "thesis": "主张足够长了",
            "chapters": [
                {
                    "title": "实测",
                    "role": "demo",
                    "slides": [
                        {
                            "title": "跑起来",
                            "verify": {
                                "command": "echo hi",
                                "expected": "hi",
                                "network": "none",
                            },
                        }
                    ],
                }
            ],
        }
    )
    v = doc["chapters"][0]["slides"][0]["verify"]
    assert v["command"] == "echo hi"
    assert v["expected"] == "hi"
    assert v["status"] == "pending"


def test_normalize_preserves_role_narration_outcome():
    doc = normalize_presentation_doc(
        {
            "title": "t",
            "thesis": "主张足够长了",
            "chapters": [
                {
                    "title": "实测",
                    "role": "demo",
                    "slides": [
                        {
                            "title": "跑起来",
                            "narration": "看这一步输出",
                            "outcome": "出现 SUCCESS",
                            "duration_ms": 3500,
                        }
                    ],
                }
            ],
        }
    )
    assert doc["chapters"][0]["role"] == "demo"
    assert doc["chapters"][0]["slides"][0]["narration"] == "看这一步输出"
    assert doc["chapters"][0]["slides"][0]["outcome"] == "出现 SUCCESS"
    assert doc["chapters"][0]["slides"][0]["duration_ms"] == 3500


def test_normalize_estimates_duration_from_narration():
    doc = normalize_presentation_doc(
        {
            "title": "t",
            "chapters": [
                {
                    "title": "c",
                    "role": "hook",
                    "slides": [{"title": "t", "narration": "甲" * 40}],
                }
            ],
        }
    )
    assert doc["chapters"][0]["slides"][0]["duration_ms"] == 40 * 120
