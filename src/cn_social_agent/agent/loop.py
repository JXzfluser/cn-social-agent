"""Lead Agent loop: mode-aware tools + Clarify/Present middleware."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from cn_social_agent.agent.middleware import (
    TurnContext,
    after_turn,
    before_tool,
    extract_artifacts_from_trace,
    extract_clarify_from_trace,
    filter_openai_tools,
)
from cn_social_agent.agent.mode import detect_mode, last_user_text
from cn_social_agent.agent.state import normalize_agent_state, plan_prompt_block
from cn_social_agent.skills.loader import SkillLoader
from cn_social_agent.tools.registry import ToolRegistry


class LLMClient(Protocol):
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]: ...


RESEARCH_COACH_PROMPT = """你是热点与选题研究助手（Agent = 扫描洞察，不做片）。
职责：扫多源热点榜（GitHub / HN / Lobsters / V2EX / Dev.to / 少数派）、insight、总结「是什么 / 谁该关注 / 值不值得做」。
扫榜用 scan_hotspot_board（source=all|github|hn|lobsters|v2ex|devto|sspai；可加 domain=ai|devtools|product|hiring）；结果已含 score/why/topic_key。
GitHub 仓用 github_repo_insight，文章/帖子用 fetch_url_text。用户要直接做片时可用 handoff_hotspot（track=koubo|presentation|journal）。
若用户像在续作旧主题（「上次那个」「继续 DeepSeek」），先 lookup_topic_assets 再决定要不要重新调研。
默认不要调用 propose_*；等用户明确说「做成短视频」或「生成知识卡片」再进入制作交接。
人口数据用 population_* 工具查阅；制作请提示用户切到短视频 / 知识卡片工坊。"""

VIDEO_COACH_PROMPT = """你是制片交接助手：先查本地资产 → 选轨 → 澄清 brief → propose → 引导去对应工坊。

本地优先（每次做片/做卡前）：
- 用户提到续作、同主题、再出一期、或明确主题名：先 lookup_topic_assets(topic=…)
- 有命中：先告诉用户本地已有期刊/证据/短视频，问「复用还是重新深采/重做」；不要默默再 scrape
- propose_knowledge_cards / propose_short_video 的返回里若带 local_assets，必须在回复里点名这些资产

轨道路由（未确认前禁止 propose）：
- 用户没说清口播还是讲解演示：先 clarify_brief(need=track|audience|scene)，问「口播短视频还是讲解演示？」
- 口播短视频（L0/L1）：clarify_brief → propose_short_video → 短视频工坊
- 讲解演示（网页舞台+OBS）：先调研（github_repo_insight / fetch_url_text），再 draft_presentation_content（带 research_notes 与 audience），再 propose_presentation；按实测弧线（hook→差异→概念→安装→实测→收束+CTA），禁止空壳口号稿
- 知识卡片：lookup_topic_assets →（github_repo_insight / fetch_url_text 调研）→ propose_knowledge_cards（带 research_notes 原文摘录 + 简短 topic）→ 工坊用原文生成种子证据，不足才补搜 → 勾选素材 →「成刊」。禁止把整段长标题当检索词

偏好：用户偏好里的 default_video_track / default_audience 可直接复用，但仍要在交接卡里写出来。讲解画幅/主题缺省用 9:16 + talent-map。

讲解演示质量铁律（draft / propose 前必须自检）：
1. 先写可反驳的 thesis，再展开章节
2. 口播稿要有论证节奏（问题→机制→证据→易错→行动），≥350 字
3. 大纲 6–8 章；演示 ≥18 步；≥8 页图示（compare/pipeline/state/cards/checklist/axes3）
4. 每条能力/论点配套「易错 + 检验」或「追问」；拒绝「赋能/干货/一文读懂」套话
5. research_notes 里的事实必须写进稿件

三种口播类型：intro 入门讲解 · compare 对比选型 · deep_analysis 深度分析。
澄清与 Present 由中间件保证——口播缺受众且缺场景时 propose_short_video 会改成 clarify_brief；讲解缺受众时 draft/propose_presentation 同样拦截。
草稿 L0 / 成片 L1 / OBS 录屏 / 卡片导出以对应工坊为主；Agent 不声称已生成视频文件。
可用 write_todos 更新计划步骤。"""


@dataclass
class AgentReply:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    mode: str = "simple"
    agent_state: dict[str, Any] = field(default_factory=dict)
    clarify: Optional[dict[str, Any]] = None
    artifacts: list[dict[str, Any]] = field(default_factory=list)


class MockLLM:
    """Deterministic LLM for offline / unit tests."""

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        model: str = "",
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        last = messages[-1].get("content", "") if messages else ""
        if isinstance(last, str) and last.strip().startswith("/tool now"):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_now",
                                    "type": "function",
                                    "function": {"name": "now", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ]
            }
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"[mock] {last}",
                    }
                }
            ]
        }


class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        skills: Optional[SkillLoader] = None,
        *,
        max_tool_rounds: int = 3,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.skills = skills
        self.max_tool_rounds = max_tool_rounds

    async def run(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "",
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        prefs: Optional[dict[str, Any]] = None,
        agent_state: Optional[dict[str, Any]] = None,
        brief: str = "",
        user_id: str = "",
        email: str = "",
        store_mode: str = "",
        insforge_db: Any = None,
    ) -> AgentReply:
        from cn_social_agent.tools.context import reset_tool_context, set_tool_context

        prefs = prefs or {}
        ctx_token = set_tool_context(
            user_id=user_id,
            email=email,
            prefs=prefs,
            store_mode=store_mode,
            insforge_db=insforge_db,
        )
        try:
            return await self._run_inner(
                messages,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                prefs=prefs,
                agent_state=agent_state,
                brief=brief,
            )
        finally:
            reset_tool_context(ctx_token)

    async def _run_inner(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str = "",
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        prefs: Optional[dict[str, Any]] = None,
        agent_state: Optional[dict[str, Any]] = None,
        brief: str = "",
    ) -> AgentReply:
        prefs = prefs or {}
        state = normalize_agent_state(agent_state)
        mode = detect_mode(messages, agent_state=state, brief=brief)
        state["mode"] = mode
        rounds = 6 if mode == "produce" else min(2, self.max_tool_rounds)

        sys_parts = [system_prompt.strip()] if system_prompt.strip() else []
        if mode == "produce":
            sys_parts.append(VIDEO_COACH_PROMPT)
            plan_block = plan_prompt_block(state)
            if plan_block:
                sys_parts.append(plan_block)
            if self.skills:
                block = self.skills.prompt_block_for_message(last_user_text(messages))
                if block:
                    sys_parts.append(block)
        else:
            sys_parts.append(RESEARCH_COACH_PROMPT)
            if self.skills:
                block = self.skills.prompt_block_for_message(last_user_text(messages))
                if block:
                    sys_parts.append(block)

        llm_messages = [
            {"role": m.get("role") or "user", "content": m.get("content") or ""}
            for m in messages
            if (m.get("role") or "") in ("user", "assistant", "system", "tool")
            and (m.get("role") != "tool")  # tool rows only via live loop
        ]
        # Keep only user/assistant turns for the seed transcript
        llm_messages = [
            m for m in llm_messages if m["role"] in ("user", "assistant", "system")
        ]

        working: list[dict[str, Any]] = []
        if sys_parts:
            working.append({"role": "system", "content": "\n\n".join(sys_parts)})
        working.extend(llm_messages)

        ctx = TurnContext(mode=mode, prefs=prefs, agent_state=state, tool_trace=[])
        openai_tools = filter_openai_tools(self.tools, mode) or None

        final_content = ""
        raw_last: dict[str, Any] = {}

        for _ in range(rounds + 1):
            kwargs: dict[str, Any] = {
                "messages": working,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            try:
                raw = await self.llm.chat_completion(**kwargs, tools=openai_tools)
            except TypeError:
                raw = await self.llm.chat_completion(**kwargs)
            raw_last = raw

            choice = (raw.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            tool_calls = message.get("tool_calls") or []
            content = message.get("content") or ""

            if not tool_calls:
                final_content = content
                break

            working.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls,
                }
            )
            for call in tool_calls:
                fn = call.get("function") or {}
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}

                name, args, forced = await before_tool(name, args, ctx, self.tools)
                if forced is not None:
                    result = forced
                else:
                    result = await self.tools.execute(name, args)
                payload = result.to_dict()
                ctx.tool_trace.append({"name": name, "arguments": args, "result": payload})
                working.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", name),
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                )
        else:
            if not final_content:
                final_content = "Tool loop exceeded max rounds."

        ctx = await after_turn(ctx, self.tools)
        clarify = extract_clarify_from_trace(ctx.tool_trace)
        if clarify:
            ctx.agent_state["last_clarify"] = {
                "question": clarify.get("question") or "",
                "need": clarify.get("need") or [],
                "topic": clarify.get("topic") or "",
            }

        return AgentReply(
            content=final_content,
            tool_calls=ctx.tool_trace,
            raw=raw_last,
            mode=mode,
            agent_state=normalize_agent_state(ctx.agent_state),
            clarify=clarify,
            artifacts=extract_artifacts_from_trace(ctx.tool_trace),
        )
