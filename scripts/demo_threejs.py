#!/usr/bin/env python3
"""Three.js 高级 Demo - 展示所有新功能"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cn_social_agent.video.pipeline import (
    render_project,
    project_dir,
)

PROJECT_ID = "threejs_demo"
DEMO_DIR = Path(__file__).parent.parent / "data" / "videos" / PROJECT_ID


async def main():
    print("=" * 60)
    print("🎬 Three.js 高级 Demo")
    print("=" * 60)

    scenes = [
        {
            "role": "hook",
            "narration": "你知道吗？现在的视频制作已经进入3D时代了。",
            "on_screen": "3D 视频革命",
            "visual": "粒子汇聚效果｜镜头从黑暗中拉远，粒子逐渐汇聚成标题文字",
            "mood": "震撼",
        },
        {
            "role": "pain",
            "narration": "传统的2D卡片视频，看起来千篇一律，观众早就审美疲劳了。",
            "on_screen": "2D 已经过时",
            "visual": "波浪网格背景｜画面从平淡的2D卡片过渡到动态波浪效果",
            "mood": "焦虑",
        },
        {
            "role": "thesis",
            "narration": "Three.js 加持的3D转场和动态背景，让你的视频瞬间高级感拉满。",
            "on_screen": "Three.js 革命",
            "visual": "旋转光环效果｜3D几何体在空间中旋转，展示技术魅力",
            "mood": "兴奋",
        },
        {
            "role": "evidence",
            "narration": "粒子汇聚、镜头穿越、故障风揭示，五种转场效果随心切换。",
            "on_screen": "5种转场效果",
            "visual": "3D方块矩阵｜不同转场效果快速切换展示",
            "mood": "专业",
        },
        {
            "role": "value",
            "narration": "不仅如此，卡片背景也能动起来。浮动粒子、波浪网格、旋转光环，让你的每个场景都独一无二。",
            "on_screen": "动态卡片背景",
            "visual": "粒子流动效果｜展示四种不同的3D卡片背景",
            "mood": "惊喜",
        },
        {
            "role": "steps",
            "narration": "使用方法超简单：设置两个环境变量，重启服务，就这么搞定。",
            "on_screen": "两行代码搞定",
            "visual": "代码界面｜展示 THREEJS_TRANSITIONS=1 和 THREEJS_CARDS=1",
            "mood": "轻松",
        },
        {
            "role": "cta",
            "narration": "想要让你的视频脱颖而出吗？赶紧试试 Three.js 增强功能吧！",
            "on_screen": "立即体验",
            "visual": "粒子汇聚成按钮｜所有粒子汇聚成一个闪耀的行动按钮",
            "mood": "号召",
        },
    ]

    print("\n📝 分镜内容：")
    for i, s in enumerate(scenes, 1):
        print(f"  {i}. [{s['role']}] {s['on_screen']}")

    print("\n🚀 开始渲染（启用 Three.js 增强）...")

    os.environ["THREEJS_TRANSITIONS"] = "1"
    os.environ["THREEJS_CARDS"] = "1"

    output_path, duration = await render_project(
        project_id=PROJECT_ID,
        title="Three.js 3D视频增强",
        scenes=scenes,
        voice="zh-CN-XiaoxiaoNeural",
        cover_hook="3D视频革命",
        hashtags=["Three.js", "视频制作", "AI"],
        cta="立即体验",
        bg_theme="night",
        motion="kenburns",
    )

    print(f"\n✅ 渲染完成！")
    print(f"   输出: {output_path}")
    print(f"   时长: {duration:.1f}s")

    print("\n🌐 生成交互式落地页...")
    landing_path = DEMO_DIR / "landing.html"
    from cn_social_agent.video.threejs.landing_page import generate_landing_page
    await generate_landing_page(
        output_path=landing_path,
        title="Three.js 3D视频增强",
        subtitle="让你的视频脱颖而出",
        sections=[
            {"title": "5种3D转场", "description": "粒子汇聚、镜头穿越、故障风揭示", "stat": "5x"},
            {"title": "4种动态背景", "description": "浮动粒子、波浪网格、旋转光环", "stat": "4x"},
            {"title": "零配置启用", "description": "两行环境变量搞定", "stat": "0"},
        ],
        template="product",
    )
    print(f"   落地页: {landing_path}")

    print("\n" + "=" * 60)
    print("🎉 Demo 完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
