"""On-demand skill selection for Agent system prompts."""

from __future__ import annotations

from cn_social_agent.skills.loader import Skill, select_skills_for_message


def _skills() -> list[Skill]:
    ids = [
        "web-video-presentation",
        "short-video-researcher",
        "github-star-growth-video",
        "deep-analysis-video",
        "short-video-director",
        "tech-saas-content",
        "hiring-insight-cards",
        "demo-echo",
    ]
    return [
        Skill(id=i, name=i, description=i, body=i, path=i, enabled=True) for i in ids
    ]


def test_idle_chat_defaults_to_director():
    picked = select_skills_for_message(_skills(), "今天天气怎么样")
    assert [s.id for s in picked] == ["short-video-director"]


def test_url_picks_researcher():
    picked = select_skills_for_message(
        _skills(), "看看这个 https://example.com/post 能拍什么"
    )
    ids = [s.id for s in picked]
    assert "short-video-researcher" in ids


def test_github_hotspot_picks_growth():
    picked = select_skills_for_message(_skills(), "扫一下热点榜 github star")
    ids = [s.id for s in picked]
    assert "github-star-growth-video" in ids


def test_deep_analysis_trigger():
    picked = select_skills_for_message(_skills(), "做一条深度分析，找规律和证据")
    ids = [s.id for s in picked]
    assert "deep-analysis-video" in ids


def test_disabled_skills_never_selected():
    skills = _skills()
    for s in skills:
        if s.id == "short-video-researcher":
            s.enabled = False
    enabled = [s for s in skills if s.enabled]
    picked = select_skills_for_message(
        enabled, "分析这个链接 https://a.com 拍短视频"
    )
    assert "short-video-researcher" not in [s.id for s in picked]


def test_presentation_trigger():
    picked = select_skills_for_message(_skills(), "按 Harness 做讲解演示，OBS 自动录")
    ids = [s.id for s in picked]
    assert "web-video-presentation" in ids


def test_tech_saas_content_trigger():
    picked = select_skills_for_message(
        _skills(), "帮我们搭技术 SaaS 内容操作系统，周更短视频"
    )
    ids = [s.id for s in picked]
    assert "tech-saas-content" in ids


def test_hiring_insight_cards_trigger():
    picked = select_skills_for_message(_skills(), "做一组招聘洞察能力图谱卡片")
    ids = [s.id for s in picked]
    assert "hiring-insight-cards" in ids
