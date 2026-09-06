from __future__ import annotations

from typing import Any

from .connectors.base import RawMaterial


CONTENT_TYPE_KEYWORDS = {
    "technical": {
        "github", "api", "sdk", "framework", "library", "tool", "cli",
        "react", "vue", "node", "python", "rust", "go", "typescript",
        "算法", "架构", "性能", "优化", "调试", "部署",
    },
    "opinion": {
        "观点", "看法", "讨论", "争议", "趋势", "未来", "思考",
        "opinion", "debate", "trend", "future", "thought",
    },
    "tutorial": {
        "教程", "入门", "指南", "实践", "案例", "手把手", "实战",
        "tutorial", "guide", "howto", "getting started", "beginner",
    },
    "news": {
        "发布", "更新", "版本", "release", "update", "launch", "announce",
    },
}


def detect_content_type(material: RawMaterial) -> str:
    text = f"{material.title} {material.summary or ''}".lower()
    tags = [t.lower() for t in material.tags]

    scores = {ctype: 0 for ctype in CONTENT_TYPE_KEYWORDS}

    for ctype, keywords in CONTENT_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                scores[ctype] += 2
            if keyword in tags:
                scores[ctype] += 3

    if material.heat > 200:
        scores["opinion"] += 2
    if material.heat > 500:
        scores["news"] += 3

    best_type = max(scores, key=scores.get)
    if scores[best_type] == 0:
        return "technical"
    return best_type


def calculate_heat_score(heat: int, content_type: str) -> int:
    thresholds = {
        "technical": [50, 150, 300, 500, 1000],
        "opinion": [100, 300, 500, 1000, 2000],
        "tutorial": [30, 100, 200, 500, 1000],
        "news": [200, 500, 1000, 2000, 5000],
    }

    t = thresholds.get(content_type, thresholds["technical"])
    for i, threshold in enumerate(t):
        if heat < threshold:
            return i + 1
    return 5


def calculate_difficulty_score(
    material: RawMaterial,
    content_type: str,
) -> int:
    base = {
        "technical": 3,
        "opinion": 2,
        "tutorial": 4,
        "news": 2,
    }

    score = base.get(content_type, 3)

    if material.summary and len(material.summary) > 300:
        score += 1
    if "github" in material.tags:
        score += 1

    return min(5, max(1, score))


def determine_time_window(heat: int, content_type: str) -> str:
    if content_type == "news":
        if heat > 1000:
            return "24h"
        return "48h"
    if content_type == "opinion":
        if heat > 500:
            return "48h"
        return "1周"
    if content_type == "tutorial":
        return "1周"
    return "不限"


def generate_angles(material: RawMaterial, content_type: str) -> list[str]:
    angles = []

    if content_type == "technical":
        angles.append("技术原理深度解析")
        if material.heat > 100:
            angles.append("为什么这么火")
        angles.append("实战应用场景")
    elif content_type == "opinion":
        angles.append("核心观点提炼")
        angles.append("正反方分析")
        angles.append("我的看法")
    elif content_type == "tutorial":
        angles.append("从零到一完整教程")
        angles.append("避坑指南")
        angles.append("进阶技巧")
    elif content_type == "news":
        angles.append("事件来龙去脉")
        angles.append("影响分析")

    return angles[:3]


def optimize_idea_generation(
    material: RawMaterial,
    content_type: str | None = None,
) -> dict[str, Any]:
    if content_type is None:
        content_type = detect_content_type(material)

    heat_score = calculate_heat_score(material.heat, content_type)
    difficulty_score = calculate_difficulty_score(material, content_type)
    time_window = determine_time_window(material.heat, content_type)
    angles = generate_angles(material, content_type)

    return {
        "content_type": content_type,
        "heat_score": heat_score,
        "difficulty_score": difficulty_score,
        "time_window": time_window,
        "angles": angles,
    }
