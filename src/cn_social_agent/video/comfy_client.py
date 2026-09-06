"""ComfyUI 客户端 — 把 ComfyUI 接入口播制片管线作为画面生成后端。

用法：
    COMFYUI_URL=http://127.0.0.1:8188  # 配置即启用
    COMFYUI_CHECKPOINT=<模型名>        # 可选，缺省自动探测第一个可用 checkpoint

render_mode="comfyui" 时：每镜用 ComfyUI txt2img 按分镜画面描述生成
1080x1920 背景图，PIL 排版（字幕/标签/进度点）照常叠加，kenburns 动效
与 ffmpeg 合成完全复用现有管线。ComfyUI 不可达时自动降级 local 模式。
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT = 240.0  # 秒：SDXL 在 CPU 上可能很慢


def comfyui_url() -> str:
    return (os.getenv("COMFYUI_URL") or "").strip().rstrip("/")


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """请求头：平台中继鉴权（COMFYUI_TOKEN → X-Token）+ 可选自定义头。"""
    h: dict[str, str] = {}
    token = (os.getenv("COMFYUI_TOKEN") or "").strip()
    if token:
        h["X-Token"] = token
    raw = (os.getenv("COMFYUI_HEADERS") or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                h.update({str(k): str(v) for k, v in parsed.items()})
        except Exception:  # noqa: BLE001
            pass
    if extra:
        h.update(extra)
    return h


def configured() -> bool:
    return bool(comfyui_url())


def _get_json(path: str, timeout: float = 8.0) -> Any:
    url = comfyui_url() + path
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def available() -> bool:
    """ComfyUI 可达性探测（/system_stats）。"""
    if not configured():
        return False
    try:
        _get_json("/system_stats")
        return True
    except Exception:  # noqa: BLE001
        return False


def _pick_checkpoint() -> str:
    explicit = (os.getenv("COMFYUI_CHECKPOINT") or "").strip()
    if explicit:
        return explicit
    try:
        info = _get_json("/object_info/CheckpointLoaderSimple")
        ckpts = (info.get("CheckpointLoaderSimple") or {}).get("input", {}).get(
            "required", {}
        ).get("ckpt_name", [[]])[0]
        if ckpts:
            return ckpts[0]
    except Exception:  # noqa: BLE001
        pass
    return "model.safetensors"


def _build_workflow(prompt: str, negative: str, width: int, height: int, seed: int, checkpoint: str) -> dict[str, Any]:
    """默认 SD/SDXL txt2img workflow（节点名兼容主流 ComfyUI 安装）。"""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "nexus_scene", "images": ["8", 0]}},
    }


_NEGATIVE = "lowres, bad anatomy, text, watermark, blurry, deformed, ugly"


def _build_scene_prompt(title: str, on_screen: str, narration: str, visual: str, bg_theme: str) -> str:
    """把分镜元数据转成画面描述（中文分镜 → 英文视觉 prompt 由模型同源处理，
    这里直接用中文描述 + 质量词，SDXL/Flux 中文理解有限，但配合排版字幕仍出可用背景）。"""
    parts = [
        "cinematic vertical composition, high quality, soft lighting,",
        f"theme: {bg_theme}",
        f"scene visual: {visual or on_screen or narration[:80]}",
        f"video about: {title[:60]}",
        "no text in image",
    ]
    return ", ".join(p for p in parts if p.strip(", "))


async def generate_to_file(
    out_png: Path,
    *,
    prompt: str = "",
    width: int = 1080,
    height: int = 1920,
    title: str = "",
    on_screen: str = "",
    narration: str = "",
    visual: str = "",
    bg_theme: str = "night",
    timeout: float = DEFAULT_TIMEOUT,
) -> Path:
    """提交 txt2img 工作流并轮询结果，下载保存到 out_png。"""
    if not configured():
        raise RuntimeError("COMFYUI_URL 未配置")
    loop = asyncio.get_running_loop()
    ckpt = await loop.run_in_executor(None, _pick_checkpoint)
    prompt_text = prompt or _build_scene_prompt(title, on_screen, narration, visual, bg_theme)
    workflow = _build_workflow(
        prompt_text,
        _NEGATIVE,
        width,
        height,
        random.randint(0, 2**31 - 1),
        ckpt,
    )

    def _submit() -> str:
        body = json.dumps({"prompt": workflow}).encode()
        req = urllib.request.Request(
            comfyui_url() + "/prompt", data=body,
            headers=_headers({"Content-Type": "application/json"}),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())["prompt_id"]

    prompt_id = await loop.run_in_executor(None, _submit)

    async def _history() -> dict[str, Any]:
        def _fetch() -> dict[str, Any]:
            return _get_json(f"/history/{prompt_id}")
        return await loop.run_in_executor(None, _fetch)

    deadline = asyncio.get_event_loop().time() + timeout
    images: list[dict[str, Any]] = []
    while asyncio.get_event_loop().time() < deadline:
        hist = await _history()
        entry = hist.get(prompt_id) or {}
        outputs = entry.get("outputs") or {}
        for node_out in outputs.values():
            for img in node_out.get("images") or []:
                if img.get("type") == "output":
                    images.append(img)
        if images:
            break
        await asyncio.sleep(1.5)
    if not images:
        raise RuntimeError(f"ComfyUI {timeout:.0f}s 内未返回图片")

    img = images[0]
    qs = urllib.parse.urlencode({
        "filename": img["filename"],
        "subfolder": img.get("subfolder", ""),
        "type": img.get("type", "output"),
    })
    out_png.parent.mkdir(parents=True, exist_ok=True)

    def _download() -> None:
        req = urllib.request.Request(f"{comfyui_url()}/view?{qs}", headers=_headers())
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_png.write_bytes(resp.read())

    await loop.run_in_executor(None, _download)
    if not out_png.is_file() or out_png.stat().st_size == 0:
        raise RuntimeError("ComfyUI 图片下载为空")
    return out_png
