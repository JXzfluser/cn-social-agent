# Short Video Workshop Design（口播短视频）

> Date: 2026-07-26  
> Status: Approved — implementing  
> Product: 短视频工坊（方案 2）

## 1. Goal

在现有 InsForge Agent Workbench 上增加具体业务：**主题 → 口播脚本/分镜 → TTS + 字幕 + ffmpeg 竖屏成片 → 下载 mp4**。

Locked decisions:

| Item | Choice |
|------|--------|
| Scenario | A — 口播/短视频脚本 → 成片 |
| Render | A — 本地 ffmpeg |
| TTS | A — edge-tts（开源/系统级） |
| UX | 独立「短视频工坊」页 + Agent 对话降为辅助 |

## 2. User flow

1. 新建项目，输入主题 / 卖点，选语气、目标时长（30/60s）、音色  
2. 生成脚本 + 分镜（可编辑单镜旁白）  
3. 一键渲染，轮询状态  
4. 下载竖屏 mp4（1080×1920），有配音与字幕  

Non-goals v1: 真人出镜、复杂转场、BGM 曲库、平台一键发布、云端文生视频。

## 3. Architecture

```
Workbench `/` (?mode=video) → /api/video/* → InsForge DB (video_projects, video_scenes)
                                            → Pipeline: LLM → edge-tts → Pillow → ffmpeg
                                            → data/videos/{project_id}/
                                            → download?inline=1 for in-page preview
`/video` redirects to `/?mode=video`
```

Reuse existing tables:

- `video_projects` (status: draft|scripting|rendering|done|failed, video_type=口播, generation_mode=local)
- `video_scenes` (content, tts_path, image_path, tts_duration_seconds)

## 4. API

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/video/projects` | List / create |
| GET/PATCH/DELETE | `/api/video/projects/{id}` | Detail (+scenes) / update / delete |
| POST | `/api/video/projects/{id}/generate` | LLM script + scenes |
| PATCH | `/api/video/scenes/{id}` | Edit scene narration |
| POST | `/api/video/projects/{id}/render` | Start render |
| GET | `/api/video/projects/{id}/status` | Status + progress |
| GET | `/api/video/projects/{id}/download` | Download mp4 (`?inline=1` for preview) |

## 5. Pipeline

1. LLM outputs JSON: `{title, full_script, scenes:[{num, narration, visual}]}`  
2. Persist script + scenes; status → scripting then draft  
3. Per scene: edge-tts → audio file; measure duration  
4. Pillow: 1080×1920 card (gradient + title snippet)  
5. ffmpeg: image+audio per scene → concat → final.mp4  
6. status → done; `output_path` set  

## 6. UI

- Single page `/` with mode tabs: **Agent** | **短视频工坊** (`?mode=video`)  
- Video mode: projects | script + **HTML5 preview** | settings  
- `/video` → redirect `/?mode=video`  

## 7. Success criteria

- [x] Topic → downloadable vertical mp4 with voice in ≤3 user steps  
- [x] Projects persist in InsForge and reopen  
- [x] Single scene narration editable before re-render  
- [x] In-page video preview after render  
- [x] v1 duration cap ≤60s  

## 8. Implementation order

1. Video store + API against existing tables  
2. generate (LLM JSON)  
3. render pipeline (tts + frames + ffmpeg)  
4. Unified workbench page + in-page preview  
5. Smoke test end-to-end  
