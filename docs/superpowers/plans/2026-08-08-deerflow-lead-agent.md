# DeerFlow Lead Agent · 实施计划

> Spec: `docs/superpowers/specs/2026-08-08-deerflow-lead-agent-design.md`

## Tasks

1. `agent/mode.py` + `agent/state.py` + `agent/middleware.py`
2. Rewrite `AgentLoop` to use middleware / tool groups / extended `AgentReply`
3. `write_todos` tool + session `agent_state` in store
4. `chat.py` persist/return agent_state；SSE done 附带
5. Workbench: Artifact Dock、折叠工具轨迹、Clarify Card
6. Tests + `scripts/smoke_lead_agent.py`

## Non-goals

No LangGraph, sandbox, subagents.
