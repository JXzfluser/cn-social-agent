# Chat → Short Video (idea handoff) Design

Date: 2026-07-26

## Goal

Agent 对话里打磨 idea；系统用 **口头提议 + 常驻行动条** 提示可做片；用户一键后 **留在对话** 建项目并生成分镜，以视频卡推进渲染/预览；短视频工坊同步同一项目。

## Approach B

1. Tool `propose_short_video(topic, selling_points?, ready)` — 仅发信号，不建片。
2. `POST /api/video/from-session` — 从会话提炼主题 → create + generate → 写入一条带 `short_video_project` 元数据的助手消息。
3. Agent 默认附带短视频策划 system 片段。
4. UI：行动条 + 建议卡 + 视频卡（渲染/预览/下载）；工坊列表可见同一项目。

## API

| Method | Path | Body / notes |
|--------|------|----------------|
| POST | `/api/video/from-session` | `{ session_id, tone?, target_seconds?, voice?, topic? }` — `topic` 可选覆盖提炼结果 |
| GET | existing download/status/render | 视频卡复用 |

422 when transcript has no usable topic.

## UI

- Composer 上方行动条：「用当前话题做短视频」
- SSE/`tool_calls` 含 `propose_short_video` → 建议卡「开始制作」
- 视频卡：分镜摘要、渲染、轮询、blob 预览、下载、链到 `?mode=video`

## Out of scope

- Agent tool 直接 render 全自动成片
- 刷新后复杂时间轴；消息里的 `short_video_project` 可恢复基础卡
