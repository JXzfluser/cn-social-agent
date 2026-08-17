"""Knowledge card categories (series + prompts + scrape hints + templates)."""

from __future__ import annotations

from typing import Any

# Default topic seeds per category (shown in UI)
DEFAULT_TOPICS: dict[str, list[str]] = {
    "hiring_insight": [
        "AI Agent 开发工程师",
        "AI 应用开发工程师",
        "AI 全栈工程师",
    ],
    "product_explain": ["AI 口播制片", "知识卡片", "Agent 工作台"],
    "skill_roadmap": ["Agent 工程", "RAG 落地", "短视频制作"],
    "industry_brief": ["AI Agent", "生成式视频", "垂直短视频"],
}

# Cover layout: classic | masthead | split | watermark
# Know layout: talent | product | roadmap | brief
CATEGORIES: dict[str, dict[str, Any]] = {
    "hiring_insight": {
        "id": "hiring_insight",
        "label": "招聘洞察",
        "short": "招聘",
        "description": "扫描岗位 JD，提炼能力图谱与市场要求",
        "topic_label": "岗位",
        "topic_placeholder": "AI Agent 开发工程师、AI 应用开发工程师",
        "action_label": "深采并成刊",
        "footer_label": "招聘洞察",
        "seriesEn": "AI TALENT MAP",
        "seriesCn": "AI 岗位能力图谱",
        "default_title": "AI 招聘能力图谱",
        "cover_layout": "classic",
        "know_layout": "talent",
        "palette": "teal",
        "decor": "rings",
        "template_label": "能力图谱",
        "scrape_suffixes": [
            "招聘 JD 岗位职责 任职要求 技能",
            "猎聘 BOSS直聘 工程师 技能要求 工作经验",
            "面试 评估 技术方案 交付物",
            "技术原理 架构 核心机制",
            "工程实践 落地案例 踩坑",
            "岗位 JD 三年经验 技术栈",
            "工具链 集成 接口 调用",
            "面试题 系统设计 可观测性 故障排查",
        ],
        "llm_role": "资深人才评估顾问与 AI 工程讲师",
        "llm_goal": (
            "生成 5–6 张可学习的能力卡片：读者应带走具体技术概念、"
            "面试/评估时用的追问标准，以及业务证据样例；卡片类型尽量多样"
        ),
        "llm_dims": "智能体编排 / 检索与知识工程 / 模型原生交付",
        "llm_teach": (
            "目标 5–6 张卡（非 3 张），至少 3 种 card_kind（concept/keypoints/steps/compare/data/quote）。"
            "禁止空洞套话（「提升竞争力」「核心能力」「精准识别」等口号）。"
            "concept（120–180字）：写清能力边界 + 与「只会调 API/多聊几轮」的区别 + 一个具体技术名"
            "（取自本期主题与参考材料里出现的框架/组件/协议，不要套用无关技术栈）。"
            "keyPoint：可用普通条目要点（3–5 行即可）；可选建议（非强制）用【机制】【易错】【检验】标注——"
            "【机制】具名步骤/组件；【易错】真实故障模式；【检验】面试官能当场验证的动作。"
            "example（80–140字）：角色→具体工具/模块→可观察交付物（含数字或产物名）。"
            "每张卡尽量带 evidenceIds；若参考材料是词典释义/百科词条，忽略之，用工程领域知识撰写。"
        ),
        "note_label": "市场信号",
        "preview": {
            "cover": {
                "title": "AI 招聘能力图谱",
                "description": "三张卡片拆解编排、检索与交付：各含定义、机制与易错点、可检验的落地案例。",
                "tags": ["Agent 编排", "RAG 工程", "全栈交付"],
                "marketNote": "示例市场信号：岗位更看重可验证的交付物，而非工具清单。",
            },
            "knowledge": [
                {
                    "topicTitle": "智能体编排与协同",
                    "concept": "Agent 按目标拆解步骤、选择工具、写入状态，失败可回退——不是多聊几轮。",
                    "keyPoint": "- 【机制】规划→工具→状态→回退\n- 【易错】无超时边界会循环调用\n- 【检验】能画出状态机并复现一次回退",
                    "flow": ["规划", "工具", "状态", "交付"],
                    "example": "规划 Agent 拆需求后，检索/编码/质检并行产出，失败回写规划节点。",
                }
            ],
        },
    },
    "product_explain": {
        "id": "product_explain",
        "label": "产品科普",
        "short": "产品",
        "description": "把产品能力讲清楚：是什么、为何重要、怎么用",
        "topic_label": "产品 / 功能",
        "topic_placeholder": "AI 口播制片、知识卡片、Agent 工作台",
        "action_label": "生成科普卡片",
        "footer_label": "产品科普",
        "seriesEn": "PRODUCT BRIEF",
        "seriesCn": "产品能力速览",
        "default_title": "产品能力速览",
        "cover_layout": "split",
        "know_layout": "product",
        "palette": "ocean",
        "decor": "grid",
        "template_label": "分栏科普",
        "scrape_suffixes": [
            "产品功能 使用场景 介绍",
            "怎么用 教程 能力",
            "用户价值 痛点 场景",
            "功能亮点 对比 竞品",
            "上手指南 操作步骤 工作流",
            "适用边界 不适用 限制",
            "落地案例 效果 交付物",
            "FAQ 常见问题 最佳实践",
        ],
        "llm_role": "B 端产品讲师与解决方案顾问",
        "llm_goal": (
            "生成 5–6 张产品学习卡片：讲清机制、适用边界与上手动作，"
            "让读者看完知道何时用、怎么用、如何判断有效；卡片类型尽量多样"
        ),
        "llm_dims": "核心机制 / 适用场景 / 上手路径",
        "llm_teach": (
            "目标 5–6 张卡（非 3 张），至少 3 种 card_kind。"
            "concept（120–180字）：产品解决什么问题、关键能力如何工作；"
            "keyPoint：①关键能力点 ②不适用场景 ③成功使用的检验信号（3–5 行）；"
            "example（80–140字）：从输入到产出的一条完整操作路径；尽量带 evidenceIds。"
        ),
        "note_label": "资料摘录",
        "preview": {
            "cover": {
                "title": "产品能力速览",
                "description": "用分栏幅面讲清产品是什么、何时用、怎么验证有效。",
                "tags": ["核心能力", "适用边界", "上手路径"],
                "marketNote": "示例摘录：先讲清价值，再给一条可跟做的路径。",
            },
            "knowledge": [
                {
                    "topicTitle": "口播制片工作流",
                    "concept": "从主题到分镜再到成片：把口播制作拆成可协作的阶段。",
                    "keyPoint": "- 【能力】一键生成分镜大纲\n- 【边界】不适合无素材纯空镜\n- 【检验】确认大纲后 5 分钟内出草稿",
                    "flow": ["主题", "分镜", "草稿", "成片"],
                    "example": "输入「OpenClaw 入门」→ 核对大纲 → 生成草稿预览 → 升级成片。",
                }
            ],
        },
    },
    "skill_roadmap": {
        "id": "skill_roadmap",
        "label": "技能路线",
        "short": "技能",
        "description": "从零到一的学习路径与关键里程碑",
        "topic_label": "技能主题",
        "topic_placeholder": "Agent 工程、RAG 落地、短视频制作",
        "action_label": "生成路线卡片",
        "footer_label": "技能路线",
        "seriesEn": "SKILL ROADMAP",
        "seriesCn": "技能成长路线",
        "default_title": "技能成长路线",
        "cover_layout": "masthead",
        "know_layout": "roadmap",
        "palette": "forest",
        "decor": "arcs",
        "template_label": "阶段路线",
        "scrape_suffixes": [
            "学习路线 入门 进阶",
            "技能树 必备能力",
            "教程 实践 项目",
            "从零到一 里程碑 阶段",
            "练习项目 作业 实战",
            "过关标准 检验 考核",
            "进阶 壁垒 难点",
            "推荐资源 书单 课程",
        ],
        "llm_role": "工程能力培养架构师与实战导师",
        "llm_goal": (
            "生成 5–6 张学习路径卡片：覆盖入门到进阶的阶段或能力面，"
            "写清必学概念、练习项目与过关标准；卡片类型尽量多样"
        ),
        "llm_dims": "基础概念 / 项目实践 / 进阶壁垒",
        "llm_teach": (
            "目标 5–6 张卡（非 3 张），至少 3 种 card_kind。"
            "concept（120–180字）：本阶段要建立的心智模型；"
            "keyPoint：①必学知识点 ②推荐练习 ③过关检验标准（3–5 行）；"
            "example（80–140字）：一个可周末完成的最小项目目标；尽量带 evidenceIds。"
        ),
        "note_label": "学习参考",
        "preview": {
            "cover": {
                "title": "技能成长路线",
                "description": "顶栏幅面 + 阶段卡片：每阶段给心智模型、练习与过关标准。",
                "tags": ["基础", "实践", "进阶"],
                "marketNote": "示例参考：用最小项目验证每一阶段，而不是只刷课。",
            },
            "knowledge": [
                {
                    "topicTitle": "阶段一 · 基础概念",
                    "concept": "先建立「工具调用 ≠ 智能体系统」的心智模型。",
                    "keyPoint": "- 【必学】状态机与工具边界\n- 【练习】手写一次失败回退\n- 【过关】能讲清规划与执行的分工",
                    "flow": ["概念", "练习", "过关"],
                    "example": "周末做一个「提问→检索→带出处回答」的最小 RAG 演示。",
                }
            ],
        },
    },
    "industry_brief": {
        "id": "industry_brief",
        "label": "行业速览",
        "short": "行业",
        "description": "热点、趋势与可执行洞察，适合快速扫读",
        "topic_label": "行业 / 话题",
        "topic_placeholder": "AI Agent、生成式视频、垂直短视频",
        "action_label": "生成速览卡片",
        "footer_label": "行业速览",
        "seriesEn": "INDUSTRY BRIEF",
        "seriesCn": "行业洞察速览",
        "default_title": "行业洞察速览",
        "cover_layout": "watermark",
        "know_layout": "brief",
        "palette": "ink",
        "decor": "bars",
        "template_label": "简报速览",
        "scrape_suffixes": [
            "行业趋势 2026",
            "热点 动态 分析",
            "机会 挑战 观点",
            "市场格局 玩家 竞争",
            "投融资 融资 估值",
            "政策 监管 合规",
            "落地案例 企业 应用",
            "风险 反证 观察指标",
        ],
        "llm_role": "行业研究分析师与知识编辑",
        "llm_goal": (
            "生成 5–6 张行业学习简报：给出可讨论的判断、关键变量与可执行动作，"
            "并附上读者可自行验证的观察点；卡片类型尽量多样"
        ),
        "llm_dims": "趋势判断 / 关键变量 / 行动建议",
        "llm_teach": (
            "目标 5–6 张卡（非 3 张），至少 3 种 card_kind。"
            "concept（120–180字）：趋势主张 + 成立前提；"
            "keyPoint：①支撑信号 ②反证风险 ③可跟踪指标（3–5 行）；"
            "example（80–140字）：团队本周可做的一个验证动作；尽量带 evidenceIds。"
        ),
        "note_label": "信号摘录",
        "preview": {
            "cover": {
                "title": "行业洞察速览",
                "description": "水印幅面适合快速扫读：判断、变量、本周动作。",
                "tags": ["趋势", "变量", "行动"],
                "marketNote": "示例信号：Agent 产品从「能聊」转向「可交付」。",
            },
            "knowledge": [
                {
                    "topicTitle": "Agent 从演示走向交付",
                    "concept": "判断：评测重心从对话质量转向可复现的任务完成率。",
                    "keyPoint": "- 【信号】企业采购要求可观测与审计\n- 【风险】Demo 场景无法迁移到生产\n- 【指标】任务成功率 / 人工介入率",
                    "flow": ["信号", "风险", "动作"],
                    "example": "本周选 1 个真实工单，跑通「自动草案 + 人工确认」闭环并记录介入次数。",
                }
            ],
        },
    },
}


def get_category(category_id: str | None) -> dict[str, Any]:
    cid = (category_id or "hiring_insight").strip() or "hiring_insight"
    return CATEGORIES.get(cid) or CATEGORIES["hiring_insight"]


# Keyword → category inference. Ordered by specificity: a hiring signal only
# wins when the text really looks like a JD, otherwise product/skill/industry.
_INFER_RULES: tuple[tuple[str, str], ...] = (
    (
        "hiring_insight",
        r"招聘|岗位|职责|任职要求|JD\b|面试|简历|薪资|求职|猎聘|BOSS直聘"
        r"|工程师招|校招|社招|人才画像|能力图谱",
    ),
    (
        "skill_roadmap",
        r"学习路线|路线图|入门|自学|从零|教程体系|技能树|进阶指南|练习|课程|书单"
        r"|如何学|怎么学|新手|上手路径|roadmap",
    ),
    (
        "industry_brief",
        r"融资|估值|投融资|市场规模|行业|赛道|政策|监管|合规|财报|营收|增长率"
        r"|竞争格局|趋势报告|周报|简报|观察|大盘|出海",
    ),
    (
        "product_explain",
        r"开源|发布|上线|工具|产品|功能|CLI|SDK|API|框架|插件|客户端|版本|v?\d+\.\d+"
        r"|GitHub|Star|安装|部署|使用教程|上手|实测|评测|对比|替代|体验|demo",
    ),
)


def infer_category(*texts: Any, default: str = "") -> str:
    """Best-effort category from topic / roles / notes.

    Returns ``default`` (may be "") when nothing matches, so callers can decide
    whether to fall back to the workshop default.
    """
    import re

    blob = " ".join(str(t or "") for t in texts if str(t or "").strip())
    if not blob.strip():
        return default
    best_id = ""
    best_hits = 0
    for cid, pattern in _INFER_RULES:
        hits = len(re.findall(pattern, blob, re.I))
        if hits > best_hits:
            best_id, best_hits = cid, hits
    if not best_id:
        return default
    # A lone generic word should not flip the series; require real signal
    if best_hits < 1:
        return default
    return best_id


def list_categories() -> list[dict[str, Any]]:
    out = []
    for c in CATEGORIES.values():
        out.append(
            {
                "id": c["id"],
                "label": c["label"],
                "short": c["short"],
                "description": c["description"],
                "topic_label": c["topic_label"],
                "topic_placeholder": c["topic_placeholder"],
                "action_label": c["action_label"],
                "note_label": c.get("note_label") or "",
                "footer_label": c.get("footer_label") or c.get("label") or "",
                "default_topics": DEFAULT_TOPICS.get(c["id"]) or [],
                "seriesEn": c.get("seriesEn") or "",
                "seriesCn": c.get("seriesCn") or "",
                "default_title": c.get("default_title") or "",
                "cover_layout": c.get("cover_layout") or "classic",
                "know_layout": c.get("know_layout") or "talent",
                "palette": c.get("palette") or "teal",
                "decor": c.get("decor") or "rings",
                "template_label": c.get("template_label") or c.get("label") or "",
                "preview": c.get("preview") or {},
            }
        )
    return out


def series_for(category_id: str | None) -> dict[str, str]:
    c = get_category(category_id)
    return {"seriesEn": c["seriesEn"], "seriesCn": c["seriesCn"]}
