"""Built-in knowledge themes for AI talent map cards."""

from __future__ import annotations

from typing import Any

THEMES: list[dict[str, Any]] = [
    {
        "id": "agent",
        "topicTitle": "智能体编排与协同",
        "concept": (
            "Agent 不是「多聊几轮」：它按目标拆解步骤、选择工具、写入状态，"
            "失败可回退。常见误解是把单次 Function Calling 当成完整智能体系统。"
        ),
        "keyBase": (
            "- 【机制】规划→工具调用（含 MCP）→状态写入→失败回退的闭环\n"
            "- 【易错】无超时/权限边界时，工具失败会循环调用或越权\n"
            "- 【检验】能画出状态机，并用 LangGraph 复现一次失败回退"
        ),
        "example": (
            "规划 Agent 拆需求后，检索/编码/质检三类执行 Agent 并行产出；"
            "质检失败回写规划节点，最终交付带来源引用的报告。"
        ),
        "flow": ["规划", "工具调用", "状态回写", "交付"],
        "keywords": [
            "langgraph",
            "autogen",
            "crewai",
            "agent",
            "多agent",
            "多智能体",
            "智能体",
            "工具调用",
            "tool use",
            "mcp",
            "任务规划",
            "编排",
            "agentic",
        ],
    },
    {
        "id": "rag",
        "topicTitle": "RAG 检索工程化",
        "concept": (
            "RAG 用「先检索后生成」把回答钉在可控语料上；质量取决于切片、召回与重排，"
            "不是换更大模型。误解：向量库上线即等于知识库可用。"
        ),
        "keyBase": (
            "- 【机制】解析→切片→Embedding→多路召回→Rerank→带出处生成\n"
            "- 【易错】切片过碎丢上下文，或只靠向量忽略关键词召回\n"
            "- 【检验】抽 20 问对比命中原文率与幻觉率是否可量化"
        ),
        "example": (
            "制度库接入后，提问先命中条款再生成答复；答案旁标注文档名与段落，"
            "人工可一键跳转复核。"
        ),
        "flow": ["切片", "召回", "重排", "带出处"],
        "keywords": [
            "rag",
            "检索增强",
            "向量",
            "知识库",
            "embedding",
            "milvus",
            "pinecone",
            "chroma",
            "rerank",
            "重排",
            "召回",
            "向量数据库",
            "faiss",
            "qdrant",
        ],
    },
    {
        "id": "fullstack",
        "topicTitle": "模型原生全栈交付",
        "concept": (
            "模型原生交付把推理做成产品能力：流式会话、路由降级、观测与部署一体，"
            "而不是页面上挂一个 Chat API。误解：会调 SDK 就算全栈 AI。"
        ),
        "keyBase": (
            "- 【机制】SSE/WebSocket 流式、会话状态、模型路由与超时降级\n"
            "- 【易错】同步阻塞易超时；缺 token/费用与错误可观测\n"
            "- 【检验】能演示「界面→API→路由→部署」闭环并压测并发"
        ),
        "example": (
            "用 FastAPI + SSE 推流，前端按 token 渲染；主模型超时自动切备用模型，"
            "并在面板展示延迟与失败原因。"
        ),
        "flow": ["界面", "流式API", "路由", "部署"],
        "keywords": [
            "全栈",
            "fullstack",
            "react",
            "vue",
            "fastapi",
            "sse",
            "websocket",
            "流式",
            "部署",
            "推理",
            "私有化",
            "next.js",
        ],
    },
]

SERIES: dict[str, str] = {
    "seriesEn": "AI TALENT MAP",
    "seriesCn": "AI 岗位能力图谱",
}

FALLBACK_COVER: dict[str, Any] = {
    "title": "AI 招聘能力图谱",
    "description": (
        "三张卡片拆解智能体编排、RAG 工程与模型原生交付："
        "各含定义、机制与易错点、可检验的落地案例。"
    ),
    "tags": ["Agent 编排", "RAG 工程", "全栈交付"],
}
