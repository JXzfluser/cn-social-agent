"""Short video workshop API routes."""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Union

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.usage.meter import KIND_L0_RENDER, KIND_L1_RENDER, record_event
from cn_social_agent.video.artifact_storage import (
    download_project_bytes,
    storage_ref_from_project,
    upload_project_final,
)
from cn_social_agent.video.pipeline import (
    apply_funnel_stamps,
    apply_render_progress,
    clear_render_progress,
    decode_script_bundle,
    delivery_snapshot,
    encode_script_bundle,
    extract_topic_from_transcript,
    funnel_snapshot,
    generate_script,
    job_from_wbmeta,
    merge_script_meta,
    missing_scene_clips,
    remux_project_final,
    render_one_scene,
    render_project,
    resolve_render_mode,
    storyboard_outline,
    unpack_scene_meta,
    utc_now_iso,
)
from cn_social_agent.video.plan import build_production_plan
from cn_social_agent.video.quality import check_final_video, suggest_scene_rerenders
from cn_social_agent.video.store import VideoStore

StoreOrErr = Union[VideoStore, web.Response]

# Throttle wbmeta progress writes (seconds between forced persists).
_PROGRESS_PERSIST_MIN_INTERVAL = 2.0


def _meter_render(
    *,
    user_id: str,
    project_id: str,
    delivery_level: str,
    scenes: int,
    status: str = "ok",
    meta: dict[str, Any] | None = None,
) -> None:
    kind = KIND_L1_RENDER if (delivery_level or "").lower() == "l1" else KIND_L0_RENDER
    record_event(
        kind,
        user_id=user_id,
        project_id=project_id,
        scenes=max(1, int(scenes or 1)),
        delivery_level=delivery_level,
        status=status,
        meta=meta,
    )


async def _persist_job_progress(
    store: VideoStore,
    *,
    user_id: str,
    project_id: str,
    job: dict[str, Any],
    force: bool = False,
) -> None:
    """Mirror in-memory job progress into project wbmeta (throttled)."""
    now = time.monotonic()
    last = float(job.get("_persist_at") or 0)
    last_scene = job.get("_persist_scene_i")
    scene_i = job.get("scene_i")
    scene_changed = scene_i is not None and scene_i != last_scene
    if not force and not scene_changed and (now - last) < _PROGRESS_PERSIST_MIN_INTERVAL:
        return
    try:
        cur = await store.get_project(user_id, project_id)
        if not cur:
            return
        script = apply_render_progress(
            cur.get("script") or "",
            progress=int(job.get("progress") or 0),
            message=str(job.get("message") or ""),
            scene_i=int(scene_i) if scene_i is not None else None,
            scene_n=int(job["scene_n"]) if job.get("scene_n") is not None else None,
            started_at=str(job.get("started_at") or "") or None,
        )
        # Keep delivery/render mode in sync while rendering.
        extras: dict[str, Any] = {}
        if job.get("delivery_level"):
            extras["delivery_level"] = job["delivery_level"]
        if job.get("render_mode"):
            extras["render_mode"] = job["render_mode"]
        if extras:
            script = merge_script_meta(script, **extras)
        await store.update_project(user_id, project_id, script=script)
        job["_persist_at"] = now
        if scene_i is not None:
            job["_persist_scene_i"] = scene_i
    except Exception:  # noqa: BLE001 — progress persist must not kill render
        pass


def _script_clear_progress(script: str, **updates: Any) -> str:
    """Apply meta updates and drop mid-render progress keys."""
    patched = merge_script_meta(script or "", **updates) if updates else (script or "")
    return clear_render_progress(patched)


async def _persist_final_with_storage(
    request: web.Request,
    *,
    user_id: str,
    project_id: str,
    local_path: str,
    script: str,
    status: str = "done",
    duration_seconds: int = 0,
) -> tuple[str, dict[str, Any]]:
    """Update project output; best-effort upload to InsForge Storage."""
    store = _video_store(request)
    assert not isinstance(store, web.Response)
    state = get_state(request)
    storage = (
        state.insforge.storage
        if state.insforge is not None and state.store_mode == "insforge"
        else None
    )
    upload_info: dict[str, Any] = {"ok": False}
    new_script = clear_render_progress(script)
    if storage is not None:
        upload_info = await upload_project_final(
            storage,
            user_id=user_id,
            project_id=project_id,
            local_path=local_path,
            script=new_script,
        )
        if upload_info.get("ok") and upload_info.get("script"):
            new_script = clear_render_progress(str(upload_info["script"]))
    await store.update_project(
        user_id,
        project_id,
        status=status,
        output_path=local_path,
        duration_seconds=int(duration_seconds),
        script=new_script,
    )
    return new_script, upload_info


def _plan_for(
    project: dict[str, Any],
    scenes: list[dict[str, Any]] | None = None,
    job: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_production_plan(project, scenes, job)


def _video_store(request: web.Request) -> StoreOrErr:
    state = get_state(request)
    if state.insforge is None or state.store_mode != "insforge":
        return web.json_response(
            {"error": "video workshop requires WORKBENCH_STORE=insforge"},
            status=503,
        )
    return VideoStore(state.insforge.db)


@require_user
async def list_or_create(request: web.Request) -> web.Response:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    if request.method == "GET":
        rows = await store.list_projects(user_id)
        projects = []
        for row in rows:
            funnel = funnel_snapshot(row)
            projects.append({**row, "funnel": funnel, **funnel})
        return web.json_response({"projects": projects})

    body = await request.json()
    topic = (body.get("topic") or "").strip()
    if not topic:
        return web.json_response({"error": "topic required"}, status=400)
    voice = body.get("voice") or "zh-CN-XiaoxiaoNeural"
    raw_type = (body.get("video_type") or "口播").strip() or "口播"
    is_pres = raw_type in ("presentation", "讲解演示", "web-presentation")
    # InsForge check: video_type IN (图文,口播,剪辑). Track flag lives in wbmeta.
    db_video_type = "口播" if is_pres else (
        raw_type if raw_type in ("图文", "口播", "剪辑") else "口播"
    )
    from cn_social_agent.video.pipeline import apply_template_defaults, encode_script_bundle

    tmpl = apply_template_defaults(
        template_id=str(body.get("template_id") or "") or None,
        target_seconds=int(body["target_seconds"]) if body.get("target_seconds") is not None else None,
        content_angle=str(body.get("content_angle") or "") or None,
        bg_theme=str(body.get("bg_theme") or "") or None,
        motion=str(body.get("motion") or "") or None,
    )
    row = await store.create_project(
        user_id,
        topic=topic,
        title=body.get("title") or "",
        target_seconds=tmpl["target_seconds"],
        voice=voice,
        tone=body.get("tone") or "活泼口播",
        video_type=db_video_type,
    )
    from cn_social_agent.video.presentation import normalize_aspect

    if is_pres:
        meta0 = {
            "full_script": "",
            "video_type": "presentation",
            "aspect": normalize_aspect(str(body.get("aspect") or "16:9")),
            "theme": (body.get("theme") or "talent-map").strip() or "talent-map",
            "phase": "content",
            "outline": "",
            "checkpoints": {},
        }
        script0 = apply_funnel_stamps(encode_script_bundle(meta0), "t_created")
    else:
        meta0 = {
            "full_script": "",
            "template_id": tmpl["template_id"],
            "content_angle": tmpl["content_angle"],
            "bg_theme": tmpl["bg_theme"],
            "motion": tmpl["motion"],
            "target_seconds": tmpl["target_seconds"],
            "threejs_transitions": body.get("threejs_transitions", False),
            "threejs_cards": body.get("threejs_cards", False),
        }
        script0 = apply_funnel_stamps(encode_script_bundle(meta0), "t_created")
    await store.update_project(
        user_id, row["id"], agnes_video_task_id=voice, script=script0, video_type=db_video_type
    )
    row = await store.get_project(user_id, row["id"])
    funnel = funnel_snapshot(row or {})
    return web.json_response(
        {**(row or {}), "funnel": funnel, **funnel, "template": tmpl},
        status=201,
    )


@require_user
async def get_project(request: web.Request) -> web.Response:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    row = await store.get_project(user_id, pid)
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    scenes = await store.list_scenes(pid)
    deep = request.query.get("deep_quality", "").lower() in ("1", "true", "yes")
    tips = await asyncio.to_thread(
        suggest_scene_rerenders, pid, scenes, deep=deep
    )
    _plain, meta = decode_script_bundle(row.get("script") or "")
    storage_ref = storage_ref_from_project(row)
    return web.json_response(
        {
            "project": row,
            "scenes": scenes,
            "delivery": delivery_snapshot(row),
            "storage": (
                {"bucket": storage_ref[0], "key": storage_ref[1]}
                if storage_ref
                else None
            ),
            "funnel": funnel_snapshot(row),
            "production_plan": _plan_for(row, scenes),
            "rerender_suggestions": tips,
            "storyboard_outline": storyboard_outline(scenes),
            "storyboard_confirmed": bool(meta.get("storyboard_confirmed")),
        }
    )


@require_user
async def patch_project(request: web.Request) -> web.Response:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    body = await request.json()
    row = await store.update_project(
        request["user"]["id"], request.match_info["id"], **body
    )
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(row)


@require_user
async def delete_project(request: web.Request) -> web.Response:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    pid = request.match_info["id"]
    ok = await store.delete_project(request["user"]["id"], pid)
    if not ok:
        return web.json_response({"error": "not found"}, status=404)
    try:
        from cn_social_agent.video.presentation import presentation_dir
        import shutil

        root = presentation_dir(pid)
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
    return web.json_response({"success": True})


def _exc_text(exc: BaseException) -> str:
    name = type(exc).__name__
    msg = str(exc).strip()
    if not msg:
        return name
    # Prefer short, actionable TTS / network messages
    if "语音合成失败" in msg or "Agnes 视频队列" in msg:
        return msg[:280]
    if "video_queue_full" in msg or "queue is full" in msg:
        return "Agnes 视频队列已满，请稍后重试本镜，或先用 L0 本地渲染出片"
    if "edge-tts" in msg or "NoAudioReceived" in msg:
        if any(x in msg for x in ("nodename", "Cannot connect", "gaierror", "Timeout", "NoAudioReceived")):
            return "语音合成失败：连不上 Microsoft TTS，请检查网络后重试"
        # Keep the real stderr/detail (already truncated upstream)
        return f"语音合成失败：{msg[:220]}"
    return f"{name}: {msg[:220]}"


def _action_error(exc: BaseException | str) -> dict:
    from cn_social_agent.action_errors import classify_error

    return classify_error(_exc_text(exc) if not isinstance(exc, str) else exc)


@require_user
async def generate(request: web.Request) -> web.Response:
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)

    body = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    tone = body.get("tone") or "活泼口播"
    from cn_social_agent.video.pipeline import apply_template_defaults

    tmpl = apply_template_defaults(
        template_id=str(body.get("template_id") or "") or None,
        target_seconds=(
            int(body["target_seconds"])
            if body.get("target_seconds") is not None
            else int(project.get("duration_seconds") or 15)
        ),
        content_angle=str(body.get("content_angle") or "") or None,
        bg_theme=str(body.get("bg_theme") or "") or None,
        motion=str(body.get("motion") or "") or None,
    )
    seconds = tmpl["target_seconds"]
    audience = (body.get("audience") or "").strip()
    scene_setting = (body.get("scene_setting") or body.get("scene") or "").strip()
    platform = (body.get("platform") or "").strip()
    cta = (body.get("cta") or "").strip()
    brief = (body.get("brief") or "").strip()
    bg_theme = tmpl["bg_theme"]
    motion = tmpl["motion"]
    content_angle = tmpl["content_angle"]
    # Phase A: scripting always pins L0 local; upgrade happens at render time
    render_mode = "local"

    await store.update_project(user_id, pid, status="scripting")
    assert state.agent is not None
    try:
        data = await generate_script(
            state.agent.llm,
            topic=project.get("topic") or "",
            tone=tone,
            seconds=seconds,
            model=body.get("model") or "",
            audience=audience,
            scene_setting=scene_setting,
            platform=platform,
            cta=cta,
            brief=brief,
            bg_theme=bg_theme,
            motion=motion,
            render_mode=render_mode,
            content_angle=content_angle,
            threejs_transitions=body.get("threejs_transitions", False),
            threejs_cards=body.get("threejs_cards", False),
        )
    except Exception as exc:  # noqa: BLE001
        fail_msg = f"generate_failed: {_exc_text(exc)}"
        script = merge_script_meta(
            project.get("script") or "",
            fail_reason=fail_msg,
            delivery_level="",
        )
        await store.update_project(user_id, pid, status="failed", script=script)
        return web.json_response(
            {"error": fail_msg, "action_error": _action_error(fail_msg)},
            status=502,
        )

    data["delivery_level"] = ""
    data["fail_reason"] = ""
    data["quality_gate_pass"] = None
    data["storyboard_confirmed"] = False
    # Preserve prior funnel stamps (e.g. t_created) then mark script ready
    _plain0, prev_meta = decode_script_bundle(project.get("script") or "")
    for key in ("t_created", "t_script_ready", "t_l0_ready", "t_l1_ready", "t_downloaded"):
        if prev_meta.get(key) and not data.get(key):
            data[key] = prev_meta[key]
    bundled = apply_funnel_stamps(encode_script_bundle(data), "t_created", "t_script_ready")
    await store.update_project(
        user_id,
        pid,
        title=data.get("title") or project.get("title"),
        script=bundled,
        duration_seconds=seconds,
        status="draft",
    )
    scenes = await store.replace_scenes(pid, data["scenes"])
    project = await store.get_project(user_id, pid)
    plain, meta = decode_script_bundle(project.get("script") or "")
    return web.json_response(
        {
            "project": project,
            "scenes": scenes,
            "script_plain": plain,
            "meta": meta,
            "delivery": delivery_snapshot(project or {}),
            "funnel": funnel_snapshot(project or {}),
            "production_plan": _plan_for(project or {}, scenes),
            "storyboard_outline": storyboard_outline(scenes),
            "storyboard_confirmed": False,
        }
    )

def _transcript_from_messages(messages: list[dict[str, Any]], *, limit: int = 40) -> str:
    lines: list[str] = []
    for m in messages[-limit:]:
        role = m.get("role") or ""
        if role not in ("user", "assistant"):
            continue
        content = (m.get("content") or "").strip()
        if not content:
            continue
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}: {content[:800]}")
    return "\n".join(lines)


@require_user
async def from_session(request: web.Request) -> web.Response:
    """Create a video project from an Agent chat session (stay-in-chat flow)."""
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    if state.agent is None:
        return web.json_response({"error": "agent not ready"}, status=503)

    body = await request.json()
    session_id = (body.get("session_id") or "").strip()
    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)

    user_id = request["user"]["id"]
    session = await state.store.get_session(user_id, session_id)
    if not session:
        return web.json_response({"error": "session not found"}, status=404)

    messages = await state.store.list_messages(user_id, session_id)
    transcript = _transcript_from_messages(messages)
    override_topic = (body.get("topic") or "").strip()
    brief_meta: dict[str, Any]
    if override_topic:
        brief_meta = {
            "ready": True,
            "topic": override_topic,
            "brief": (body.get("brief") or body.get("selling_points") or "").strip(),
            "audience": (body.get("audience") or "").strip(),
            "scene_setting": (body.get("scene_setting") or body.get("scene") or "").strip(),
            "platform": (body.get("platform") or "").strip(),
            "cta": (body.get("cta") or "").strip(),
            "reason": "override",
        }
    else:
        try:
            brief_meta = await extract_topic_from_transcript(
                state.agent.llm,
                transcript=transcript,
                model=body.get("model") or session.get("model") or "",
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"error": f"extract_failed: {exc}"}, status=502
            )

    if not brief_meta.get("ready") or not (brief_meta.get("topic") or "").strip():
        return web.json_response(
            {
                "error": brief_meta.get("reason") or "对话里还没有可拍的主题",
                "brief": brief_meta,
            },
            status=422,
        )

    topic = brief_meta["topic"].strip()
    tone = body.get("tone") or "活泼口播"
    voice = body.get("voice") or "zh-CN-XiaoxiaoNeural"
    from cn_social_agent.video.pipeline import apply_template_defaults

    tmpl = apply_template_defaults(
        template_id=str(body.get("template_id") or "") or None,
        target_seconds=int(body["target_seconds"]) if body.get("target_seconds") is not None else None,
        content_angle=str(body.get("content_angle") or "") or None,
        bg_theme=str(body.get("bg_theme") or "") or None,
        motion=str(body.get("motion") or "") or None,
    )
    seconds = tmpl["target_seconds"]
    audience = (body.get("audience") or brief_meta.get("audience") or "").strip()
    scene_setting = (
        body.get("scene_setting") or body.get("scene") or brief_meta.get("scene_setting") or ""
    ).strip()
    platform = (body.get("platform") or brief_meta.get("platform") or "").strip()
    cta = (body.get("cta") or brief_meta.get("cta") or "").strip()
    brief = (body.get("brief") or brief_meta.get("brief") or "").strip()
    bg_theme = tmpl["bg_theme"]
    motion = tmpl["motion"]
    content_angle = tmpl["content_angle"]
    render_mode = "local"  # Phase A: from-session creates L0 path only

    row = await store.create_project(
        user_id,
        topic=topic,
        title=topic[:40],
        target_seconds=seconds,
        voice=voice,
        tone=tone,
    )
    pid = row["id"]
    await store.update_project(user_id, pid, agnes_video_task_id=voice, status="scripting")

    try:
        data = await generate_script(
            state.agent.llm,
            topic=topic,
            tone=tone,
            seconds=seconds,
            model=body.get("model") or "",
            audience=audience,
            scene_setting=scene_setting,
            platform=platform,
            cta=cta,
            brief=brief,
            bg_theme=bg_theme,
            motion=motion,
            render_mode=render_mode,
            content_angle=content_angle,
        )
    except Exception as exc:  # noqa: BLE001
        await store.update_project(user_id, pid, status="failed")
        return web.json_response({"error": f"generate_failed: {_exc_text(exc)}"}, status=502)

    data["storyboard_confirmed"] = False
    bundled = apply_funnel_stamps(encode_script_bundle(data), "t_created", "t_script_ready")
    await store.update_project(
        user_id,
        pid,
        title=data.get("title") or topic[:40],
        script=bundled,
        duration_seconds=seconds,
        status="draft",
    )
    scenes = await store.replace_scenes(pid, data["scenes"])
    project = await store.get_project(user_id, pid)

    outline = storyboard_outline(scenes)
    scene_preview = "\n".join(
        f"{r['scene_num']}. [{r['role']}] {r['on_screen'] or r['narration_preview']}"
        for r in outline[:8]
    )
    card_text = (
        f"已根据当前对话创建短视频项目「{project.get('title') or topic}」。\n"
        f"主题：{topic}\n"
        f"{('受众：' + audience + chr(10)) if audience else ''}"
        f"{('场景：' + scene_setting + chr(10)) if scene_setting else ''}"
        f"{('卖点：' + brief + chr(10)) if brief else ''}"
        f"分镜大纲（{len(outline)} 镜）：\n{scene_preview or '（无）'}\n"
        "下一步：到工作台核对分镜 → 点「确认分镜」→ 再生成草稿(L0)。"
    )
    saved = await state.store.add_message(
        user_id,
        session_id,
        role="assistant",
        content=card_text,
        tool_calls=[
            {
                "name": "short_video_project",
                "arguments": {"session_id": session_id},
                "result": {
                    "success": True,
                    "data": {
                        "project_id": pid,
                        "topic": topic,
                        "brief": brief_meta.get("brief") or "",
                        "status": project.get("status") or "draft",
                        "title": project.get("title") or topic,
                        "delivery_level": None,
                        "render_mode": "local",
                    },
                },
            }
        ],
    )

    return web.json_response(
        {
            "project": project,
            "scenes": scenes,
            "brief": brief_meta,
            "message": saved,
            "delivery": delivery_snapshot(project or {}),
            "funnel": funnel_snapshot(project or {}),
            "production_plan": _plan_for(project or {}, scenes),
            "storyboard_outline": outline,
            "storyboard_confirmed": False,
        },
        status=201,
    )


@require_user
async def patch_scene(request: web.Request) -> web.Response:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    scene_id = request.match_info["id"]
    scene = await store.get_scene(scene_id)
    if not scene:
        return web.json_response({"error": "not found"}, status=404)
    project = await store.get_project(request["user"]["id"], scene["project_id"])
    if not project:
        return web.json_response({"error": "forbidden"}, status=403)
    body = await request.json()
    fields: dict[str, Any] = {}
    if body.get("content") is not None or body.get("narration") is not None:
        fields["content"] = body.get("content") or body.get("narration") or ""
    # Merge on_screen / visual / mood / role into packed image_path meta
    meta = unpack_scene_meta(str(scene.get("image_path") or ""))
    touched_meta = False
    for key in ("on_screen", "visual", "mood", "role"):
        if key in body and body.get(key) is not None:
            meta[key] = str(body.get(key) or "").strip()
            touched_meta = True
    if body.get("image_path") and str(body.get("image_path")).strip().startswith("{"):
        fields["image_path"] = body.get("image_path")
    elif touched_meta:
        from cn_social_agent.video.pipeline import pack_scene_meta

        fields["image_path"] = pack_scene_meta(meta)
    updated = await store.update_scene(scene_id, **fields)
    # Editing beats invalidates confirmation
    if fields:
        await store.update_project(
            request["user"]["id"],
            scene["project_id"],
            script=merge_script_meta(project.get("script") or "", storyboard_confirmed=False),
        )
    return web.json_response(updated)


@require_user
async def confirm_storyboard(request: web.Request) -> web.Response:
    """Checkpoint A1: user confirms outline before any L0/L1 render."""
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    scenes = await store.list_scenes(pid)
    if not scenes:
        return web.json_response({"error": "no scenes; generate first"}, status=400)
    script = merge_script_meta(project.get("script") or "", storyboard_confirmed=True)
    project = await store.update_project(user_id, pid, script=script)
    return web.json_response(
        {
            "project": project,
            "scenes": scenes,
            "storyboard_confirmed": True,
            "storyboard_outline": storyboard_outline(scenes),
            "production_plan": _plan_for(project or {}, scenes),
            "delivery": delivery_snapshot(project or {}),
        }
    )


@require_user
async def render_scene(request: web.Request) -> web.Response:
    """Re-render one scene then remux final.mp4 (Phase B)."""
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    scene_id = request.match_info["scene_id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    scene = await store.get_scene(scene_id)
    if not scene or str(scene.get("project_id")) != str(pid):
        return web.json_response({"error": "scene not found"}, status=404)

    scenes = await store.list_scenes(pid)
    _plain_gate, meta_gate = decode_script_bundle(project.get("script") or "")
    if not meta_gate.get("storyboard_confirmed"):
        return web.json_response(
            {
                "error": "storyboard_not_confirmed",
                "message": "请先核对并确认分镜大纲，再渲染",
                "storyboard_confirmed": False,
            },
            status=409,
        )
    jobs: dict[str, Any] = state.video_jobs
    job_key = pid
    if jobs.get(job_key, {}).get("status") == "rendering":
        return web.json_response(
            {"error": "project already rendering", "job": jobs[job_key]},
            status=409,
        )

    body: dict[str, Any] = {}
    try:
        if request.can_read_body:
            raw = await request.json()
            if isinstance(raw, dict):
                body = raw
    except Exception:  # noqa: BLE001
        body = {}

    delivery_intent = (body.get("delivery_level") or "").strip().lower()
    override_mode = (body.get("render_mode") or "").strip()
    engine = (body.get("engine") or "").strip() or None
    refresh = (body.get("refresh") or "all").strip().lower()
    if delivery_intent == "l1":
        override_mode = "agnes-video"
    elif delivery_intent == "l0":
        override_mode = "local"

    _plain, meta = decode_script_bundle(project.get("script") or "")
    scene_meta = unpack_scene_meta(str(scene.get("image_path") or ""))
    # 'auto'/empty → pick best available engine on demand (agnes > comfy > local)
    render_mode = resolve_render_mode(
        override_mode
        or scene_meta.get("scene_render_mode")
        or meta.get("render_mode")
        or ""
    )
    delivery_level = "l1" if render_mode == "agnes-video" else "l0"
    idx = int(scene.get("scene_num") or 0)
    if idx <= 0:
        return web.json_response({"error": "invalid scene_num"}, status=400)

    started_at = utc_now_iso()
    label = "成片" if delivery_level == "l1" else "分镜草稿"
    start_msg = (
        f"后台升级分镜 {idx}（{label}）…"
        if delivery_level == "l1"
        else f"重渲分镜 {idx}（{delivery_level}）…"
    )
    jobs[job_key] = {
        "status": "rendering",
        "progress": 5,
        "message": start_msg,
        "scene_id": scene_id,
        "scene_num": idx,
        "scene_i": idx,
        "scene_n": len(scenes),
        "delivery_level": delivery_level,
        "render_mode": render_mode,
        "started_at": started_at,
    }
    await store.update_project(
        user_id,
        pid,
        status="rendering",
        script=apply_render_progress(
            merge_script_meta(
                project.get("script") or "",
                render_mode=render_mode,
                delivery_level=delivery_level,
                fail_reason="",
            ),
            progress=5,
            message=start_msg,
            scene_i=idx,
            scene_n=len(scenes),
            started_at=started_at,
        ),
    )

    async def _job() -> None:
        try:
            voice = project.get("agnes_video_task_id") or "zh-CN-XiaoxiaoNeural"
            result = await render_one_scene(
                project_id=pid,
                scene=scene,
                idx=idx,
                total_scenes=len(scenes),
                title=project.get("title") or project.get("topic") or "视频",
                voice=voice,
                cover_hook=meta.get("cover_hook") or "",
                hashtags=meta.get("hashtags") or [],
                cta=meta.get("cta") or "",
                bg_theme=meta.get("bg_theme") or "night",
                motion=meta.get("motion") or "kenburns",
                render_mode=render_mode,
                refresh=refresh,
                engine=engine,
            )
            await store.update_scene(
                scene_id,
                tts_path=result["tts_path"],
                image_path=result["image_path"],
                tts_duration_seconds=result["tts_duration_seconds"],
            )
            jobs[job_key] = {
                **jobs[job_key],
                "progress": 70,
                "message": f"分镜 {idx} 完成，检查缺失镜…",
            }
            await _persist_job_progress(
                store, user_id=user_id, project_id=pid, job=jobs[job_key], force=True
            )
            missing = missing_scene_clips(pid, len(scenes))
            filled: list[int] = []
            if missing:
                jobs[job_key]["message"] = (
                    f"分镜 {idx} 完成，补渲缺失镜 {','.join(str(i) for i in missing)}…"
                )
                await _persist_job_progress(
                    store, user_id=user_id, project_id=pid, job=jobs[job_key], force=True
                )
                by_num = {int(s.get("scene_num") or 0): s for s in scenes}
                for miss_idx in missing:
                    sc = by_num.get(miss_idx)
                    if not sc or not sc.get("id"):
                        continue
                    fill = await render_one_scene(
                        project_id=pid,
                        scene=sc,
                        idx=miss_idx,
                        total_scenes=len(scenes),
                        title=project.get("title") or project.get("topic") or "视频",
                        voice=voice,
                        cover_hook=meta.get("cover_hook") or "",
                        hashtags=meta.get("hashtags") or [],
                        cta=meta.get("cta") or "",
                        bg_theme=meta.get("bg_theme") or "night",
                        motion=meta.get("motion") or "kenburns",
                        render_mode="local",
                        refresh="all",
                    )
                    await store.update_scene(
                        str(sc["id"]),
                        tts_path=fill["tts_path"],
                        image_path=fill["image_path"],
                        tts_duration_seconds=fill["tts_duration_seconds"],
                    )
                    filled.append(miss_idx)
                jobs[job_key]["message"] = (
                    f"已自动补渲缺失镜：{','.join(str(i) for i in filled) or '无'}，合并成片…"
                    if filled
                    else "合并成片…"
                )
            else:
                jobs[job_key]["message"] = f"分镜 {idx} 完成，合并成片…"
            await _persist_job_progress(
                store, user_id=user_id, project_id=pid, job=jobs[job_key], force=True
            )
            out, total = await remux_project_final(pid, len(scenes))

            gate_pass: Any = None
            if delivery_level == "l1" or meta.get("delivery_level") == "l1":
                # Re-check final when project was/is L1 oriented
                gate = check_final_video(Path(out), expected_audio_seconds=float(total))
                gate_pass = gate.passed
                if not gate.passed and delivery_level == "l1":
                    reason = "；".join(gate.reasons) or "quality gate failed"
                    fail_msg = f"未通过成片质检，仍是草稿：{reason}"
                    script = _script_clear_progress(
                        (await store.get_project(user_id, pid) or project).get("script")
                        or "",
                        fail_reason=fail_msg,
                        quality_gate_pass=False,
                        delivery_level="l0",
                    )
                    await store.update_project(
                        user_id,
                        pid,
                        status="failed",
                        output_path=out,
                        duration_seconds=int(total),
                        script=script,
                    )
                    jobs[job_key] = {
                        "status": "failed",
                        "progress": 0,
                        "message": fail_msg,
                        "fail_reason": fail_msg,
                        "output_path": out,
                        "scene_num": idx,
                        "delivery_level": "l0",
                        "quality": gate.as_dict(),
                    }
                    _meter_render(
                        user_id=user_id,
                        project_id=pid,
                        delivery_level=delivery_level,
                        scenes=1,
                        status="quality_fail",
                        meta={"scene_num": idx, "mode": "scene"},
                    )
                    return

            # Keep project delivery_level if already l1; scene upgrade doesn't force whole project to l1 label unless all Agnes
            script = merge_script_meta(
                (await store.get_project(user_id, pid) or project).get("script") or "",
                fail_reason="",
                quality_gate_pass=gate_pass,
            )
            script, upload_info = await _persist_final_with_storage(
                request,
                user_id=user_id,
                project_id=pid,
                local_path=out,
                script=script,
                status="done",
                duration_seconds=int(total),
            )
            tips = suggest_scene_rerenders(pid, await store.list_scenes(pid))
            fill_note = (
                f"；已自动补渲缺失镜 {','.join(str(i) for i in filled)}" if filled else ""
            )
            jobs[job_key] = {
                "status": "done",
                "progress": 100,
                "message": f"分镜 {idx} 已更新并合并{fill_note}",
                "output_path": out,
                "scene_num": idx,
                "delivery_level": delivery_level,
                "render_mode": render_mode,
                "rerender_suggestions": tips,
                "backfilled_scenes": filled,
                "storage": {
                    "ok": bool(upload_info.get("ok")),
                    "bucket": upload_info.get("bucket"),
                    "key": upload_info.get("key"),
                    "error": upload_info.get("error"),
                },
            }
            _meter_render(
                user_id=user_id,
                project_id=pid,
                delivery_level=delivery_level,
                scenes=1 + len(filled),
                status="ok",
                meta={"scene_num": idx, "mode": "scene", "backfilled": filled},
            )
        except Exception as exc:  # noqa: BLE001
            reason = _exc_text(exc)
            try:
                cur = await store.get_project(user_id, pid)
                script = _script_clear_progress(
                    (cur or project).get("script") or "", fail_reason=reason
                )
                await store.update_project(
                    user_id, pid, status="failed", script=script
                )
            except Exception:  # noqa: BLE001
                await store.update_project(user_id, pid, status="failed")
            jobs[job_key] = {
                "status": "failed",
                "progress": 0,
                "message": reason,
                "fail_reason": reason,
                "scene_num": idx,
            }
            _meter_render(
                user_id=user_id,
                project_id=pid,
                delivery_level=delivery_level,
                scenes=1,
                status="error",
                meta={"scene_num": idx, "mode": "scene", "error": reason[:200]},
            )

    asyncio.create_task(_job())
    return web.json_response(jobs[job_key], status=202)


@require_user
async def render(request: web.Request) -> web.Response:
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    scenes = await store.list_scenes(pid)
    if not scenes:
        return web.json_response({"error": "no scenes; generate first"}, status=400)

    _plain_gate, meta_gate = decode_script_bundle(project.get("script") or "")
    if not meta_gate.get("storyboard_confirmed"):
        return web.json_response(
            {
                "error": "storyboard_not_confirmed",
                "message": "请先核对并确认分镜大纲，再生成草稿",
                "storyboard_outline": storyboard_outline(scenes),
                "storyboard_confirmed": False,
            },
            status=409,
        )

    jobs: dict[str, Any] = state.video_jobs
    if jobs.get(pid, {}).get("status") == "rendering":
        return web.json_response(jobs[pid])

    override_mode = ""
    delivery_intent = ""
    try:
        if request.can_read_body:
            rb = await request.json()
            if isinstance(rb, dict):
                override_mode = (rb.get("render_mode") or "").strip()
                delivery_intent = (rb.get("delivery_level") or "").strip().lower()
    except Exception:  # noqa: BLE001
        override_mode = ""

    # Map delivery_level shortcut → render_mode
    if delivery_intent == "l1":
        override_mode = "agnes-video"
    elif delivery_intent == "l0":
        override_mode = "local"

    started_at = utc_now_iso()
    # 'auto' (or empty) resolves to the best available engine on demand:
    # agnes-video (if configured) > comfyui (if reachable) > local
    preview_mode = resolve_render_mode(override_mode)
    preview_level = "l1" if preview_mode == "agnes-video" else "l0"
    start_msg = (
        "后台升级成片中…"
        if preview_level == "l1"
        else "生成分镜草稿中…"
    )
    jobs[pid] = {
        "status": "rendering",
        "progress": 0,
        "message": start_msg,
        "delivery_level": preview_level if override_mode else None,
        "render_mode": override_mode or None,
        "started_at": started_at,
    }
    await store.update_project(
        user_id,
        pid,
        status="rendering",
        script=apply_render_progress(
            merge_script_meta(project.get("script") or "", fail_reason=""),
            progress=0,
            message=start_msg,
            started_at=started_at,
        ),
    )

    async def _job() -> None:
        try:
            async def on_progress(i: int, n: int, msg: str) -> None:
                jobs[pid] = {
                    **jobs.get(pid, {}),
                    "status": "rendering",
                    "progress": int(i / max(n, 1) * 100),
                    "message": msg,
                    "scene_i": i,
                    "scene_n": n,
                    "delivery_level": delivery_level,
                    "render_mode": render_mode,
                    "started_at": started_at,
                }
                await _persist_job_progress(
                    store, user_id=user_id, project_id=pid, job=jobs[pid]
                )

            # Refresh project in case script was patched
            proj = await store.get_project(user_id, pid) or project
            voice = proj.get("agnes_video_task_id") or "zh-CN-XiaoxiaoNeural"
            _plain, meta = decode_script_bundle(proj.get("script") or "")
            # 'auto'/empty → pick best available engine on demand (agnes > comfy > local)
            render_mode = resolve_render_mode(override_mode or meta.get("render_mode") or "")
            delivery_level = "l1" if render_mode == "agnes-video" else "l0"
            label = "成片" if delivery_level == "l1" else "分镜草稿"
            running_msg = (
                f"后台升级{label}（{render_mode}）…"
                if delivery_level == "l1"
                else f"渲染{label}（{render_mode}）…"
            )

            meta_updates = {
                "render_mode": render_mode,
                "delivery_level": delivery_level,
                "fail_reason": "",
                "quality_gate_pass": None,
                "full_script": _plain,
            }
            script0 = encode_script_bundle({**meta, **meta_updates})
            script0 = apply_render_progress(
                script0,
                progress=5,
                message=running_msg,
                started_at=started_at,
            )
            await store.update_project(user_id, pid, script=script0)

            jobs[pid] = {
                "status": "rendering",
                "progress": 5,
                "message": running_msg,
                "delivery_level": delivery_level,
                "render_mode": render_mode,
                "started_at": started_at,
            }

            if meta.get("threejs_transitions"):
                os.environ["THREEJS_TRANSITIONS"] = "1"
            else:
                os.environ.pop("THREEJS_TRANSITIONS", None)
            if meta.get("threejs_cards"):
                os.environ["THREEJS_CARDS"] = "1"
            else:
                os.environ.pop("THREEJS_CARDS", None)

            out, total = await render_project(
                project_id=pid,
                title=proj.get("title") or proj.get("topic") or "视频",
                scenes=scenes,
                voice=voice,
                cover_hook=meta.get("cover_hook") or "",
                hashtags=meta.get("hashtags") or [],
                cta=meta.get("cta") or "",
                bg_theme=meta.get("bg_theme") or "night",
                motion=meta.get("motion") or "kenburns",
                render_mode=render_mode,
                on_progress=on_progress,
            )
            for sc in scenes:
                if sc.get("id"):
                    await store.update_scene(
                        sc["id"],
                        tts_path=sc.get("tts_path") or "",
                        image_path=sc.get("image_path") or "",
                        tts_duration_seconds=sc.get("tts_duration_seconds") or 0,
                    )

            gate_pass: Any = None
            gate_reasons: list[str] = []
            if delivery_level == "l1":
                jobs[pid] = {
                    "status": "rendering",
                    "progress": 95,
                    "message": "成片质检中…",
                    "delivery_level": delivery_level,
                    "render_mode": render_mode,
                    "started_at": started_at,
                }
                await _persist_job_progress(
                    store, user_id=user_id, project_id=pid, job=jobs[pid], force=True
                )
                gate = check_final_video(
                    Path(out), expected_audio_seconds=float(total)
                )
                gate_pass = gate.passed
                gate_reasons = gate.reasons
                if not gate.passed:
                    reason = "；".join(gate.reasons) or "quality gate failed"
                    fail_msg = f"未通过成片质检，仍是草稿：{reason}"
                    script = _script_clear_progress(
                        (await store.get_project(user_id, pid) or proj).get("script")
                        or "",
                        render_mode=render_mode,
                        delivery_level="l0",
                        fail_reason=fail_msg,
                        quality_gate_pass=False,
                    )
                    await store.update_project(
                        user_id,
                        pid,
                        status="failed",
                        output_path=out,
                        duration_seconds=int(total),
                        script=script,
                    )
                    jobs[pid] = {
                        "status": "failed",
                        "progress": 0,
                        "message": fail_msg,
                        "output_path": out,
                        "delivery_level": "l0",
                        "render_mode": render_mode,
                        "quality_gate_pass": False,
                        "fail_reason": fail_msg,
                        "quality": gate.as_dict(),
                    }
                    _meter_render(
                        user_id=user_id,
                        project_id=pid,
                        delivery_level=delivery_level,
                        scenes=len(scenes),
                        status="quality_fail",
                        meta={"mode": "full"},
                    )
                    return

            script = merge_script_meta(
                (await store.get_project(user_id, pid) or proj).get("script") or "",
                render_mode=render_mode,
                delivery_level=delivery_level,
                fail_reason="",
                quality_gate_pass=gate_pass if delivery_level == "l1" else None,
            )
            ready_key = "t_l1_ready" if delivery_level == "l1" else "t_l0_ready"
            script = apply_funnel_stamps(script, ready_key)
            script, upload_info = await _persist_final_with_storage(
                request,
                user_id=user_id,
                project_id=pid,
                local_path=out,
                script=script,
                status="done",
                duration_seconds=int(total),
            )
            jobs[pid] = {
                "status": "done",
                "progress": 100,
                "message": f"{label}已就绪",
                "output_path": out,
                "delivery_level": delivery_level,
                "render_mode": render_mode,
                "quality_gate_pass": gate_pass,
                "fail_reason": "",
                "storage": {
                    "ok": bool(upload_info.get("ok")),
                    "bucket": upload_info.get("bucket"),
                    "key": upload_info.get("key"),
                    "error": upload_info.get("error"),
                },
            }
            _meter_render(
                user_id=user_id,
                project_id=pid,
                delivery_level=delivery_level,
                scenes=len(scenes),
                status="ok",
                meta={"mode": "full"},
            )
        except Exception as exc:  # noqa: BLE001
            reason = _exc_text(exc)
            try:
                cur = await store.get_project(user_id, pid)
                script = _script_clear_progress(
                    (cur or project).get("script") or "",
                    fail_reason=reason,
                )
                await store.update_project(
                    user_id, pid, status="failed", script=script
                )
            except Exception:  # noqa: BLE001
                await store.update_project(user_id, pid, status="failed")
            jobs[pid] = {
                "status": "failed",
                "progress": 0,
                "message": reason,
                "fail_reason": reason,
            }
            _meter_render(
                user_id=user_id,
                project_id=pid,
                delivery_level=delivery_intent or "l0",
                scenes=len(scenes),
                status="error",
                meta={"mode": "full", "error": reason[:200]},
            )

    asyncio.create_task(_job())
    return web.json_response(jobs[pid], status=202)


@require_user
async def status(request: web.Request) -> web.Response:
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    pid = request.match_info["id"]
    project = await store.get_project(request["user"]["id"], pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    delivery = delivery_snapshot(project)
    job = state.video_jobs.get(pid)
    if not job:
        restored = job_from_wbmeta(project, delivery)
        if restored:
            job = restored
        else:
            job = {
                "status": project.get("status"),
                "progress": 100 if project.get("status") == "done" else 0,
                "message": delivery.get("fail_reason")
                or (
                    f"{delivery.get('delivery_label')}已就绪"
                    if project.get("status") == "done"
                    else ""
                ),
                "output_path": project.get("output_path") or "",
                "delivery_level": delivery.get("delivery_level"),
                "render_mode": delivery.get("render_mode"),
                "quality_gate_pass": delivery.get("quality_gate_pass"),
                "fail_reason": delivery.get("fail_reason") or "",
            }
    else:
        job = {
            **job,
            "delivery_level": job.get("delivery_level") or delivery.get("delivery_level"),
            "render_mode": job.get("render_mode") or delivery.get("render_mode"),
            "fail_reason": job.get("fail_reason") or delivery.get("fail_reason") or "",
            "quality_gate_pass": job.get("quality_gate_pass")
            if "quality_gate_pass" in job
            else delivery.get("quality_gate_pass"),
        }
    fail = str(job.get("fail_reason") or "").strip()
    if fail:
        job["action_error"] = _action_error(fail)
    try:
        scenes = await store.list_scenes(pid)
    except Exception as exc:  # noqa: BLE001 — InsForge blip during poll
        return web.json_response(
            {
                "project": project,
                "job": job,
                "delivery": delivery,
                "funnel": funnel_snapshot(project),
                "production_plan": _plan_for(project, [], job),
                "rerender_suggestions": [],
                "warning": f"scenes_unavailable: {_exc_text(exc)}",
            }
        )
    tips = await asyncio.to_thread(suggest_scene_rerenders, pid, scenes, deep=False)
    return web.json_response(
        {
            "project": project,
            "job": job,
            "delivery": delivery,
            "funnel": funnel_snapshot(project),
            "production_plan": _plan_for(project, scenes, job),
            "rerender_suggestions": tips,
        }
    )


@require_user
async def download(request: web.Request) -> web.StreamResponse:
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    path = project.get("output_path") or ""
    local = Path(path) if path else None
    inline = request.query.get("inline", "").lower() in ("1", "true", "yes")
    suffix = (local.suffix.lower() if local else "") or ".mp4"
    ctype = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mkv": "video/x-matroska",
    }.get(suffix, "application/octet-stream")
    filename = f'{project.get("title") or "video"}{suffix}'
    disposition = (
        f'inline; filename="{filename}"'
        if inline
        else f'attachment; filename="{filename}"'
    )

    # First download stamp (ignore store errors — still serve the file)
    try:
        stamped = apply_funnel_stamps(project.get("script") or "", "t_downloaded")
        if stamped != (project.get("script") or ""):
            await store.update_project(user_id, pid, script=stamped)
    except Exception:  # noqa: BLE001
        pass

    if local is not None and local.is_file():
        return web.FileResponse(
            str(local),
            headers={
                "Content-Type": ctype,
                "Content-Disposition": disposition,
                "Accept-Ranges": "bytes",
            },
        )

    # Fallback: InsForge Storage when local scratch was cleaned
    state = get_state(request)
    storage = (
        state.insforge.storage
        if state.insforge is not None and state.store_mode == "insforge"
        else None
    )
    blob = await download_project_bytes(storage, project)
    if blob:
        return web.Response(
            body=blob,
            headers={
                "Content-Type": ctype,
                "Content-Disposition": disposition,
                "Content-Length": str(len(blob)),
            },
        )
    ref = storage_ref_from_project(project)
    hint = f"storage={ref[0]}/{ref[1]}" if ref else "no local file or storage key"
    return web.json_response({"error": "output not ready", "hint": hint}, status=404)


async def video_page(_request: web.Request) -> web.Response:
    # Unified workbench: keep /video as alias into main page video mode.
    raise web.HTTPFound("/?mode=video")


@require_user
async def publish_copy(request: web.Request) -> web.Response:
    """LLM 生成发布包：3 个标题候选 + 话题标签 + 简介（对标剪映/度加的一站式发布）。"""
    state = get_state(request)
    store = _video_store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    project = await store.get_project(user_id, pid)
    if not project:
        return web.json_response({"error": "not found"}, status=404)
    llm = getattr(state.agent, "llm", None) if state.agent else None
    if llm is None:
        return web.json_response({"error": "llm not configured"}, status=503)
    topic = (project.get("title") or project.get("topic") or "").strip()
    plain, meta = decode_script_bundle(project.get("script") or "")
    # 分镜旁白优先：它可能已被人工改写（剧本/客户稿），比生成时的 full_script 更忠实
    try:
        rows = await store.list_scenes(pid)
        scene_text = " ".join(
            str((r.get("content") or "").strip()) for r in sorted(rows, key=lambda x: int(x.get("scene_num") or 0))
        )
        if len(scene_text.strip()) > len(plain.strip()):
            plain = scene_text
    except Exception:  # noqa: BLE001
        pass
    hook = str(meta.get("cover_hook") or "")[:120]
    platform = str(meta.get("platform") or "抖音")
    system = (
        "你是资深短视频运营。先判断内容体裁（剧情短剧 / 知识讲解 / 观点口播），再据此写发布文案："
        "剧情短剧要突出人物处境、悬念钩子与情绪共鸣；知识讲解突出能学到什么；观点口播突出反常识。"
        "只输出 JSON：{\"titles\":[\"标题1\",\"标题2\",\"标题3\"],"
        "\"hashtags\":[\"#标签\",...最多6个],\"description\":\"80字内的简介，带行动号召\"}。"
        "标题口语化有钩子，标签贴合平台流量习惯，必须与正文内容一致。"
    )
    user = f"平台：{platform}\n主题：{topic}\n开场钩子：{hook}\n正文前1200字：{plain[:1200]}"
    try:
        data = await asyncio.wait_for(
            llm.chat_completion(
                [{"role": "system", "content": system}, {"role": "user", "content": user}]
            ),
            timeout=90,
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"llm_failed: {exc}"}, status=502)
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") if isinstance(data, dict) else data
    text = str(content or "")
    import json as _json
    import re as _re

    pack: dict[str, Any] = {}
    try:
        pack = _json.loads(text)
    except _json.JSONDecodeError:
        m = _re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                pack = _json.loads(m.group(0))
            except _json.JSONDecodeError:
                pack = {}
    titles = [str(t).strip() for t in (pack.get("titles") or []) if str(t).strip()][:3]
    hashtags = [str(h).strip() for h in (pack.get("hashtags") or []) if str(h).strip()][:6]
    description = str(pack.get("description") or "").strip()[:300]
    if not titles:
        return web.json_response({"error": "empty pack, try again"}, status=502)
    return web.json_response(
        {"ok": True, "titles": titles, "hashtags": hashtags, "description": description}
    )


def setup_video_routes(app: web.Application) -> None:
    from cn_social_agent.api.presentation_routes import setup_presentation_routes

    setup_presentation_routes(app)
    app.router.add_get("/video", video_page)
    app.router.add_post("/api/video/from-session", from_session)
    app.router.add_post("/api/video/projects/{id}/publish-copy", publish_copy)
    app.router.add_route("GET", "/api/video/projects", list_or_create)
    app.router.add_route("POST", "/api/video/projects", list_or_create)
    app.router.add_get("/api/video/projects/{id}", get_project)
    app.router.add_patch("/api/video/projects/{id}", patch_project)
    app.router.add_delete("/api/video/projects/{id}", delete_project)
    app.router.add_post("/api/video/projects/{id}/generate", generate)
    app.router.add_post("/api/video/projects/{id}/confirm-storyboard", confirm_storyboard)
    app.router.add_post("/api/video/projects/{id}/render", render)
    app.router.add_post(
        "/api/video/projects/{id}/scenes/{scene_id}/render", render_scene
    )
    app.router.add_get("/api/video/projects/{id}/status", status)
    app.router.add_get("/api/video/projects/{id}/download", download)
    app.router.add_patch("/api/video/scenes/{id}", patch_scene)
