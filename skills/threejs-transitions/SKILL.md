---
id: threejs-transitions
name: Three.js Transitions, Cards & Landing Pages
description: 3D transitions, enhanced card rendering, and interactive landing pages using Three.js.
---

# Three.js Transitions, Cards & Landing Pages

Enhance video renders with cinematic 3D transitions, visually rich card backgrounds,
and interactive scroll-driven landing pages. Uses Three.js for WebGL rendering.

## Architecture

```
Scene A (MP4) → Three.js Transition (MP4) → Scene B (MP4)
                     ↓
              Node.js render script
              (Three.js + Puppeteer)
                     ↓
              Frame sequence → ffmpeg → MP4
```

## Available Transitions

| id | feel | duration | use_case |
|----|------|----------|----------|
| `particle_converge` | 粒子汇聚成文字 | 1.5s | 开场、重点强调 |
| `camera_flythrough` | 镜头穿越场景 | 2.0s | 场景切换、空间感 |
| `glitch_reveal` | 故障风揭示 | 1.0s | 技术吐槽、快节奏 |
| `light_sweep` | 光扫效果 | 1.5s | 产品展示、科技感 |
| `depth_blur` | 景深模糊过渡 | 1.2s | 深度分析、沉稳 |

## Available Card Effects

| id | feel | use_case |
|----|------|----------|
| `particles` | 浮动粒子 | 通用、干货 |
| `waves` | 波浪网格 | 痛点、对比 |
| `grid` | 3D 方块矩阵 | 步骤、背景 |
| `rings` | 旋转光环 | 论点、验证 |
| `none` | 无效果 | 简洁场景 |

## Available Landing Page Templates

| id | feel | use_case |
|----|------|----------|
| `product` | 粒子流 + 网格地面 | 产品发布、SaaS |
| `tech` | 旋转方块矩阵 | 技术展示、开发者工具 |
| `minimal` | 旋转光环 | 极简风格、品牌展示 |

## Usage

### As a Skill

The agent will automatically suggest transitions based on scene role:
- `hook` → `particle_converge` or `glitch_reveal`
- `pain` → `depth_blur`
- `value/steps` → `light_sweep`
- `cta` → `particle_converge`

Card effects are mapped by role:
- `hook/value/cta` → `particles`
- `pain/compare/pitfall` → `waves`
- `context/steps` → `grid`
- `thesis/proof` → `rings`

### Manual Integration

```python
from cn_social_agent.video.threejs.renderer import render_transition
from cn_social_agent.video.threejs.card_renderer import render_card_sync

await render_transition(
    transition_type="particle_converge",
    text="核心论点",
    accent_color=(255, 90, 70),
    output_path=Path("/tmp/transition.mp4"),
    duration=1.5,
    resolution=(1080, 1920),
)

render_card_sync(
    output_path=Path("/tmp/card.png"),
    title="场景标题",
    subtitle="核心信息",
    role="value",
    scene_num=1,
    total=5,
    accent_color=(255, 90, 70),
    bg_color=(10, 14, 18),
    effect="particles",
    reveal=1.0,
)

from cn_social_agent.video.threejs.landing_page import generate_landing_page_sync

generate_landing_page_sync(
    output_path=Path("/tmp/landing.html"),
    title="产品发布",
    subtitle="下一代开发工具",
    sections=[
        {"title": "极速开发", "description": "提升10倍效率", "stat": "10x"},
        {"title": "智能协作", "description": "AI驱动的团队协作", "stat": "AI+"},
    ],
    accent_color=(255, 90, 70),
    bg_color=(10, 14, 18),
    template="product",
)
```

## Dependencies

- Node.js 18+
- Puppeteer (npm)
- Three.js (npm)
- ffmpeg (system)

## Configuration

Environment variables:
- `THREEJS_TRANSITIONS=1`: Enable 3D transitions between scenes
- `THREEJS_CARDS=1`: Enable 3D card backgrounds (falls back to Pillow on error)
- `CHROME_PATH`: Override Chrome executable path
