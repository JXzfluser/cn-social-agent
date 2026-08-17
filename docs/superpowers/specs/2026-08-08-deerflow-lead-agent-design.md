# DeerFlow Lead Agent · 设计（循环 + 工作台）

> Date: 2026-08-08  
> Status: Approved for implementation  
> Related: [artifact-first](./2026-08-08-artifact-first-producer-design.md)、DeerFlow Harness

## 1. 目标

把 Agent 从「可调工具的聊天」升级为制片 **Lead Agent**：Plan → Clarify → Act → Present；Chat 与工坊共用计划/产物真相。

## 2. 非目标

- 不迁移 DeerFlow / LangGraph
- 不上 sandbox / subagent / ACP
- 不上完整多类目 Memory 流水线（沿用 prefs）
- 不恢复工坊参数墙

## 3. 模式

| 模式 | 判定 | 行为 |
|------|------|------|
| simple | 无做片意图 | 不注入 VIDEO_COACH；工具仅 research+now；rounds=2 |
| produce | URL/热点/做片关键词/已有 project/brief | 全套中间件；rounds=6；注入计划摘要 |

## 4. 中间件

1. **ClarifyMiddleware**：`propose_short_video` 在 audience+scene 皆空（且 prefs 无默认受众）时硬拦截 → 强制 clarify 结果  
2. **PresentMiddleware**：本轮成功 propose（ready）且未 present → 自动补 `present_video_artifact`（若已有 project_id）或标记 `needs_present`  
3. **ToolGroupFilter**：按模式过滤 OpenAI tools  
4. **PlanMiddleware**：维护会话 todos；有 `active_project_id` 时以 `production_plan` 为真相

## 5. 会话 agent_state

```json
{
  "mode": "produce",
  "todos": [{"id":"topic","label":"选题","status":"done"}],
  "active_project_id": null,
  "last_clarify": null
}
```

## 6. UI

- Agent 右侧增加 Artifact Dock（绑定 active_project_id）
- 工具轨迹默认折叠
- clarify_brief → Clarify Card（快捷填受众/场景）

## 7. 验收

- 无受众无场景无法真正 propose  
- 制片模式 Chat 返回 agent_state + mini-plan  
- Present 卡片必出（或 needs_present 引导做成片）  
- 单测 + smoke
