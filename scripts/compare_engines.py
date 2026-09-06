"""Compare video engines by rendering the same scene with different engines.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/compare_engines.py \
        --scene '{"scene_num":1,"content":"测试内容","role":"hook"}' \
        --title "测试标题" \
        --engines agnes local
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cn_social_agent.video.engines import available_engines, get_engine
from cn_social_agent.video.quality import check_scene_quality


async def render_with_engine(
    engine_name: str,
    scene: dict,
    title: str,
    output_dir: Path,
) -> dict:
    engine_cls = get_engine(engine_name)
    if engine_cls is None:
        return {"engine": engine_name, "error": f"engine '{engine_name}' not found"}

    if not engine_cls.configured():
        return {"engine": engine_name, "error": "engine not configured"}

    start = time.monotonic()
    try:
        from cn_social_agent.video.pipeline import render_one_scene

        result = await render_one_scene(
            project_id=f"compare_{engine_name}",
            scene=scene,
            idx=1,
            total_scenes=1,
            title=title,
            render_mode="agnes-video" if engine_name == "agnes" else "local",
            engine=engine_name,
        )
        elapsed = time.monotonic() - start

        clip_path = Path(result.get("clip_path", ""))
        quality = None
        if clip_path.is_file():
            quality = check_scene_quality(scene, clip_path, role=scene.get("role", "value"))

        return {
            "engine": engine_name,
            "elapsed_seconds": round(elapsed, 2),
            "clip_path": str(clip_path),
            "tts_duration": result.get("tts_duration_seconds"),
            "quality": quality.as_dict() if quality else None,
        }
    except Exception as e:
        return {"engine": engine_name, "error": str(e), "elapsed_seconds": time.monotonic() - start}


async def main():
    parser = argparse.ArgumentParser(description="Compare video engines")
    parser.add_argument("--scene", required=True, help="JSON scene dict")
    parser.add_argument("--title", default="对比测试", help="Video title")
    parser.add_argument(
        "--engines",
        nargs="+",
        default=None,
        help=f"Engines to compare (default: all available: {available_engines()})",
    )
    parser.add_argument("--output-dir", default="/tmp/engine_compare", help="Output directory")
    args = parser.parse_args()

    scene = json.loads(args.scene)
    engines = args.engines or available_engines()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Comparing engines: {engines}")
    print(f"Scene: {scene}")
    print()

    results = []
    for engine_name in engines:
        print(f"Rendering with {engine_name}...")
        result = await render_with_engine(engine_name, scene, args.title, output_dir)
        results.append(result)
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result['elapsed_seconds']}s, quality: {result.get('quality', {}).get('passed', 'N/A')}")
        print()

    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for r in results:
        engine = r["engine"]
        if "error" in r:
            print(f"  {engine}: FAILED - {r['error']}")
        else:
            q = r.get("quality") or {}
            print(f"  {engine}: {r['elapsed_seconds']}s, "
                  f"duration={r.get('tts_duration')}s, "
                  f"quality_passed={q.get('passed', 'N/A')}")

    out_file = output_dir / "results.json"
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nDetailed results: {out_file}")


if __name__ == "__main__":
    asyncio.run(main())
