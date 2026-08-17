"""Presentation-track endpoints (scaffold / checkpoints / build / serve / import / publish)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from aiohttp import web

from cn_social_agent.api.deps import get_state, require_user
from cn_social_agent.usage.meter import KIND_VIDEO_PUBLISH, record_event
from cn_social_agent.video.pipeline import (
    decode_script_bundle,
    encode_script_bundle,
)
from cn_social_agent.video.plan import build_production_plan
from cn_social_agent.video.presentation import (
    apply_content_pack,
    checkpoint_confirmed,
    dist_dir,
    half_auto_douyin_payload,
    import_final_mp4,
    is_presentation,
    load_content_json,
    normalize_aspect,
    obs_checklist,
    presentation_dir,
    require_checkpoint,
    run_build,
    save_content_json,
    scaffold_project,
    set_checkpoint,
    synthesize_presentation_narrations,
)
from cn_social_agent.video.store import VideoStore

# merge_script_meta is the real name
def _store(request: web.Request) -> VideoStore | web.Response:
    state = get_state(request)
    if state.insforge is None or state.store_mode != "insforge":
        return web.json_response(
            {"error": "video workshop requires WORKBENCH_STORE=insforge"},
            status=503,
        )
    return VideoStore(state.insforge.db)


async def _load(request: web.Request) -> tuple[VideoStore, str, dict[str, Any]] | web.Response:
    store = _store(request)
    if isinstance(store, web.Response):
        return store
    user_id = request["user"]["id"]
    pid = request.match_info["id"]
    row = await store.get_project(user_id, pid)
    if not row:
        return web.json_response({"error": "not found"}, status=404)
    return store, user_id, row


def _meta(project: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    return decode_script_bundle(project.get("script") or "")


@require_user
async def confirm_checkpoint(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    name = (request.match_info.get("name") or "").strip().lower()
    if name not in ("a1", "b"):
        return web.json_response({"error": "checkpoint must be a1 or b"}, status=400)
    body: dict[str, Any] = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)

    extra: dict[str, Any] = {}
    if name == "a1":
        # Ensure content exists or accept from body
        if body.get("outline"):
            meta["outline"] = body["outline"]
        if body.get("full_script") is not None:
            plain = str(body.get("full_script") or "")
        if body.get("theme"):
            meta["theme"] = body["theme"]
        if body.get("aspect"):
            meta["aspect"] = normalize_aspect(str(body["aspect"]))
        if body.get("dev_mode"):
            meta["dev_mode"] = body["dev_mode"]
        if not (meta.get("outline") or "").strip() or not plain.strip():
            return web.json_response(
                {"error": "A1 需要口播稿（full_script）与大纲（outline）"},
                status=400,
            )
        meta["phase"] = "build"
    else:
        synthesize = bool(body.get("synthesize_audio", False))
        extra["synthesize_audio"] = synthesize
        meta["phase"] = "audio" if synthesize else "record"

    meta = set_checkpoint(meta, name, confirmed=True, **extra)
    meta["video_type"] = "presentation"
    meta["full_script"] = plain
    script = encode_script_bundle(meta)
    # encode uses full_script as body — ensure
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response(
        {
            "project": row,
            "checkpoints": meta.get("checkpoints"),
            "production_plan": build_production_plan(row or project, []),
        }
    )


@require_user
async def scaffold(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)
    err = require_checkpoint(meta, "a1")
    if err:
        return web.json_response({"error": err}, status=409)
    aspect = normalize_aspect(str(meta.get("aspect") or "16:9"))
    theme = str(meta.get("theme") or "talent-map")
    try:
        dest = await asyncio.to_thread(
            scaffold_project,
            project["id"],
            aspect=aspect,
            theme=theme,
            title=project.get("title") or project.get("topic") or "",
        )
    except FileNotFoundError as e:
        return web.json_response({"error": str(e)}, status=500)
    meta["presentation_path"] = str(dest)
    meta["aspect"] = aspect
    meta["theme"] = theme
    meta["video_type"] = "presentation"
    meta["phase"] = "build"
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response(
        {
            "ok": True,
            "path": str(dest),
            "project": row,
            "production_plan": build_production_plan(row or project, []),
        }
    )


@require_user
async def build(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)
    err = require_checkpoint(meta, "a1")
    if err:
        return web.json_response({"error": err}, status=409)
    root = presentation_dir(project["id"])
    if not (root / "package.json").is_file():
        aspect = normalize_aspect(str(meta.get("aspect") or "9:16"))
        theme = str(meta.get("theme") or "talent-map")
        try:
            await asyncio.to_thread(
                scaffold_project,
                project["id"],
                aspect=aspect,
                theme=theme,
                title=project.get("title") or project.get("topic") or "",
            )
        except FileNotFoundError as e:
            return web.json_response({"error": str(e)}, status=500)
        meta["presentation_path"] = str(presentation_dir(project["id"]))
        meta["aspect"] = aspect
        meta["theme"] = theme
    result = await asyncio.to_thread(run_build, project["id"])
    if not result.get("ok"):
        return web.json_response(
            {"ok": False, "error": "build failed", "log": result.get("log") or ""},
            status=500,
        )
    meta["presentation_built"] = True
    meta["presentation_path"] = str(presentation_dir(project["id"]))
    meta["video_type"] = "presentation"
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response(
        {
            "ok": True,
            "dist": result.get("dist"),
            "log": result.get("log"),
            "project": row,
            "preview_path": f"/api/video/projects/{project['id']}/presentation/",
            "production_plan": build_production_plan(row or project, []),
        }
    )


@require_user
async def synthesize_audio(request: web.Request) -> web.Response:
    """Generate per-slide TTS for presentation audio / auto modes."""
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)
    body: dict[str, Any] = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    voice = str(
        body.get("voice")
        or meta.get("voice")
        or "zh-CN-XiaoxiaoNeural"
    ).strip() or "zh-CN-XiaoxiaoNeural"
    try:
        out = await synthesize_presentation_narrations(project["id"], voice=voice)
    except FileNotFoundError as e:
        return web.json_response({"error": str(e)}, status=400)
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    except Exception as e:  # noqa: BLE001
        return web.json_response(
            {"error": f"TTS 失败：{type(e).__name__}: {e}"},
            status=500,
        )
    meta["audio_ready"] = True
    meta["voice"] = voice
    meta["video_type"] = "presentation"
    meta["narration_total_ms"] = int(out.get("total_ms") or 0)
    meta["narration_qc"] = out.get("qc") or {}
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response(
        {
            **out,
            "project": row,
            "production_plan": build_production_plan(row or project, []),
            "hint": (
                f"已合成 {out.get('count') or 0} 段旁白"
                + (
                    f" · 总时长约 {int((out.get('total_ms') or 0) / 1000)}s"
                    if out.get("total_ms")
                    else ""
                )
                + (
                    " · 时间轴质检通过"
                    if (out.get("qc") or {}).get("ok")
                    else " · 时间轴质检有问题，请看 qc.issues"
                )
            ),
        }
    )


@require_user
async def serve_presentation(request: web.Request) -> web.StreamResponse:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    _store_o, _uid, project = loaded
    root = dist_dir(project["id"])
    if not (root / "index.html").is_file():
        return web.json_response(
            {"error": "演示尚未构建，请先 scaffold + build"},
            status=404,
        )
    rel = (request.match_info.get("path") or "").lstrip("/")
    if not rel or rel.endswith("/"):
        target = root / "index.html"
    else:
        target = (root / rel).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError:
            return web.json_response({"error": "invalid path"}, status=400)
    if not target.is_file():
        # SPA fallback
        target = root / "index.html"
    return web.FileResponse(target)


@require_user
async def import_video(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)

    reader = await request.multipart()
    src_path: Path | None = None
    tmp: Path | None = None
    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            tmp_dir = presentation_dir(project["id"]) / "_upload"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            filename = (part.filename or "upload.webm").strip() or "upload.webm"
            ext = Path(filename).suffix.lower()
            if ext not in (".mp4", ".webm", ".mkv"):
                ext = ".webm"
            tmp = tmp_dir / f"upload{ext}"
            with tmp.open("wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            src_path = tmp
        elif part.name == "path":
            raw = (await part.text()).strip()
            if raw:
                src_path = Path(raw)

    if not src_path:
        return web.json_response({"error": "file or path required"}, status=400)
    try:
        dest = await asyncio.to_thread(import_final_mp4, project["id"], src_path)
    except (FileNotFoundError, ValueError) as e:
        return web.json_response({"error": str(e)}, status=400)

    from cn_social_agent.video.presentation_qc import run_dual_qc, run_final_qc

    final_gate = await asyncio.to_thread(
        run_final_qc,
        project["id"],
        output_path=str(dest),
        meta=meta,
    )
    dual = await asyncio.to_thread(
        run_dual_qc,
        project["id"],
        meta=meta,
        output_path=str(dest),
    )

    meta["video_type"] = "presentation"
    meta["quality_gate_pass"] = bool(final_gate.get("ok"))
    meta["quality_final"] = {
        "passed": bool(final_gate.get("ok")),
        "reasons": final_gate.get("reasons") or [],
        "metrics": final_gate.get("metrics") or {},
    }
    meta["quality_dual"] = {
        "ok": bool(dual.get("ok")),
        "hint": dual.get("hint") or "",
        "content": dual.get("content") or {},
        "final": dual.get("final") or {},
        "quality_items": dual.get("quality_items") or [],
        "blockers": dual.get("blockers") or [],
        "has_final": dual.get("has_final"),
    }
    if final_gate.get("ok"):
        meta["phase"] = "publish"
        status = "done"
    else:
        meta["phase"] = "record"
        status = "review"
        meta["fail_reason"] = "未通过成片质检：" + "；".join(
            (final_gate.get("reasons") or [])[:3] or ["quality gate failed"]
        )

    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(
        user_id,
        project["id"],
        script=script,
        output_path=str(dest),
        status=status,
        duration_seconds=int(float((final_gate.get("metrics") or {}).get("video_duration") or 0)),
    )
    return web.json_response(
        {
            "ok": bool(final_gate.get("ok")),
            "output_path": str(dest),
            "project": row,
            "quality": final_gate,
            "dual_qc": dual,
            "production_plan": build_production_plan(row or project, []),
            "hint": (
                "成片已导入且通过质检"
                if final_gate.get("ok")
                else (
                    "成片已保存但未过质检："
                    + "；".join((final_gate.get("reasons") or [])[:3] or ["请重录"])
                )
            ),
        }
    )


@require_user
async def presentation_meta(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    _s, _u, project = loaded
    plain, meta = _meta(project)
    aspect = normalize_aspect(str(meta.get("aspect") or "16:9"))
    base = f"/api/video/projects/{project['id']}/presentation/"
    preview = str(request.url.origin()).rstrip("/") + base
    return web.json_response(
        {
            "is_presentation": is_presentation(project, meta),
            "aspect": aspect,
            "theme": meta.get("theme") or "talent-map",
            "phase": meta.get("phase") or "content",
            "checkpoints": meta.get("checkpoints") or {},
            "a1": checkpoint_confirmed(meta, "a1"),
            "b": checkpoint_confirmed(meta, "b"),
            "preview_url": preview,
            "obs": obs_checklist(aspect=aspect, preview_url=preview + "?auto=1"),
            "built": (dist_dir(project["id"]) / "index.html").is_file(),
            "has_output": bool(project.get("output_path")),
            "audio_ready": bool(meta.get("audio_ready"))
            or bool(
                list((presentation_dir(project["id"]) / "public" / "audio").glob("*.mp3"))
                if (presentation_dir(project["id"]) / "public" / "audio").is_dir()
                else []
            ),
            "outline": meta.get("outline") or "",
            "script_preview": plain[:500],
            "quality_gate_pass": meta.get("quality_gate_pass"),
            "quality_dual": meta.get("quality_dual"),
            "verification": meta.get("verification"),
            "fail_reason": meta.get("fail_reason") or "",
            "production_plan": build_production_plan(project, []),
        }
    )


@require_user
async def presentation_qc(request: web.Request) -> web.Response:
    """Run dual QC (content + final) for presentation project."""
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)

    from cn_social_agent.video.presentation_qc import run_dual_qc

    dual = await asyncio.to_thread(
        run_dual_qc,
        project["id"],
        meta=meta,
        output_path=str(project.get("output_path") or ""),
    )
    meta["quality_dual"] = {
        "ok": bool(dual.get("ok")),
        "hint": dual.get("hint") or "",
        "content_ok": bool((dual.get("content") or {}).get("ok")),
        "final_ok": bool((dual.get("final") or {}).get("ok")),
        "content": dual.get("content") or {},
        "final": dual.get("final") or {},
        "quality_items": dual.get("quality_items") or [],
        "blockers": dual.get("blockers") or [],
        "has_final": dual.get("has_final"),
    }
    if dual.get("has_final"):
        meta["quality_gate_pass"] = bool((dual.get("final") or {}).get("ok"))
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response({**dual, "project": row})



@require_user
async def presentation_verify(request: web.Request) -> web.Response:
    """Run demo verify steps in the sandbox and persist statuses (验证门禁)."""
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)

    from cn_social_agent.video.verification import run_verification

    result = await run_verification(project["id"], meta=meta)
    report = result.get("report") or {}
    meta["verification"] = {
        "ok": bool(report.get("ok")),
        "declared": report.get("declared", 0),
        "passed": report.get("passed", 0),
        "failed": report.get("failed", 0),
        "pending": report.get("pending", 0),
        "unavailable": report.get("unavailable", 0),
        "hint": result.get("hint") or "",
        "docker": bool(result.get("docker")),
    }
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response({**result, "project": row})


@require_user
async def publish_douyin(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    body: dict[str, Any] = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    title = (body.get("title") or project.get("title") or project.get("topic") or "").strip()
    hashtags = body.get("hashtags") or meta.get("hashtags") or []
    if not isinstance(hashtags, list):
        hashtags = []
    description = (body.get("description") or plain[:200] or title).strip()
    video_path = project.get("output_path") or ""
    if not video_path or not Path(video_path).is_file():
        return web.json_response({"error": "请先导入成片 mp4"}, status=400)
    if meta.get("quality_gate_pass") is False:
        return web.json_response(
            {
                "error": "成片未过质检，请重录/重导后再发抖音",
                "fail_reason": meta.get("fail_reason") or "",
            },
            status=409,
        )

    # Prefer VideoPublisher when registered
    result: dict[str, Any]
    try:
        from cn_social_agent.platforms.douyin.publisher import DouyinVideoPublisher

        pub = DouyinVideoPublisher()
        owner = user_id
        result = await pub.publish_video(
            user_id=owner,
            title=title,
            video_path=Path(video_path),
            hashtags=[str(h) for h in hashtags],
            description=description,
            meta=meta,
        )
    except Exception as e:  # noqa: BLE001
        result = half_auto_douyin_payload(
            title=title, hashtags=[str(h) for h in hashtags], description=description
        )
        result["message"] = f"{result['message']}（{type(e).__name__}: {e}）"

    meta["publish"] = {
        "platform": result.get("platform"),
        "status": result.get("status"),
        "external_id": result.get("external_id") or "",
        "url": result.get("url") or "",
        "message": result.get("message") or "",
    }
    meta["video_type"] = meta.get("video_type") or project.get("video_type") or "口播"
    if is_presentation(project, meta):
        meta["video_type"] = "presentation"
        meta["phase"] = "publish"
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    record_event(
        KIND_VIDEO_PUBLISH,
        user_id=user_id,
        project_id=project["id"],
        status=str(result.get("status") or "ok"),
        meta={"platform": result.get("platform") or "douyin"},
    )
    return web.json_response(
        {"result": result, "project": row, "production_plan": build_production_plan(row or project, [])}
    )




@require_user
async def apply_pack(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)
    err = require_checkpoint(meta, "a1")
    if err:
        return web.json_response({"error": err}, status=409)
    body: dict[str, Any] = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    pack_id = (body.get("pack_id") or "ai-hiring-map").strip()
    root = presentation_dir(project["id"])
    if not (root / "package.json").is_file():
        aspect = str(meta.get("aspect") or "9:16")
        theme = str(meta.get("theme") or "talent-map")
        title = str(project.get("topic") or meta.get("title") or "讲解演示")
        await asyncio.to_thread(
            scaffold_project,
            project["id"],
            aspect=aspect,
            theme=theme,
            title=title,
        )
    try:
        await asyncio.to_thread(apply_content_pack, project["id"], pack_id)
    except FileNotFoundError as e:
        return web.json_response({"error": str(e)}, status=404)
    # rebuild
    result = await asyncio.to_thread(run_build, project["id"])
    pack_json = load_content_json(project["id"])
    pack_theme = str(pack_json.get("theme") or meta.get("theme") or "talent-map")
    meta["presentation_built"] = bool(result.get("ok"))
    meta["content_pack"] = pack_id
    meta["theme"] = pack_theme
    meta["video_type"] = "presentation"
    if pack_json.get("outline"):
        meta["outline"] = pack_json.get("outline")
    if pack_json.get("full_script"):
        meta["full_script"] = pack_json.get("full_script")
    script = encode_script_bundle({**meta, "full_script": meta.get("full_script") or plain})
    row = await store.update_project(user_id, project["id"], script=script)
    status = 200 if result.get("ok") else 500
    return web.json_response(
        {
            "ok": bool(result.get("ok")),
            "pack_id": pack_id,
            "log": result.get("log"),
            "project": row,
            "preview_path": f"/api/video/projects/{project['id']}/presentation/",
            "production_plan": build_production_plan(row or project, []),
        },
        status=status,
    )



@require_user
async def draft_content(request: web.Request) -> web.Response:
    """LLM deep-draft: thesis + outline + script + rich chapters; optional save."""
    state = get_state(request)
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    if not is_presentation(project, meta):
        return web.json_response({"error": "not a presentation project"}, status=400)
    body: dict[str, Any] = {}
    if request.can_read_body:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
    topic = str(
        body.get("topic")
        or project.get("topic")
        or project.get("title")
        or meta.get("title")
        or ""
    ).strip()
    if not topic:
        return web.json_response({"error": "topic required"}, status=400)
    if state.agent is None or getattr(state.agent, "llm", None) is None:
        return web.json_response({"error": "llm not configured"}, status=503)

    from cn_social_agent.knowledge.assets import resolve_pack_research_notes
    from cn_social_agent.video.presentation_content import generate_presentation_content

    base_notes = str(body.get("research_notes") or meta.get("research_notes") or "").strip()
    pack_id = str(body.get("pack_id") or meta.get("evidence_pack_id") or "").strip()
    evidence_meta: dict[str, Any] = {}
    # Auto-inject local evidence when pack_id given, or when notes empty and topic matches
    if pack_id or not base_notes:
        try:
            resolved = await resolve_pack_research_notes(
                pack_id=pack_id,
                topic=topic if not pack_id else "",
                user_id=user_id,
                email=str((request.get("user") or {}).get("email") or ""),
            )
        except Exception:  # noqa: BLE001
            resolved = {"ok": False, "notes": ""}
        ev_notes = str(resolved.get("notes") or "").strip()
        if ev_notes:
            evidence_meta = {
                "evidence_pack_id": resolved.get("pack_id") or pack_id,
                "evidence_source": resolved.get("source") or "",
                "evidence_count": resolved.get("count") or 0,
            }
            if base_notes:
                base_notes = ev_notes + "\n\n——\n补充调研：\n" + base_notes
            else:
                base_notes = ev_notes

    try:
        out = await generate_presentation_content(
            state.agent.llm,
            topic=topic,
            research_notes=base_notes,
            audience=str(body.get("audience") or meta.get("audience") or ""),
            angle=str(body.get("angle") or ""),
            aspect=str(body.get("aspect") or meta.get("aspect") or "9:16"),
            theme=str(body.get("theme") or meta.get("theme") or "talent-map"),
            model=str(body.get("model") or project.get("model") or ""),
        )
    except Exception as exc:  # noqa: BLE001
        return web.json_response({"error": f"draft_failed: {exc}"}, status=502)

    doc = out.get("content") or {}
    apply = body.get("apply", True)
    if apply:
        save_content_json(project["id"], doc)
        meta["outline"] = str(doc.get("outline") or meta.get("outline") or "")
        meta["thesis"] = str(doc.get("thesis") or "")
        meta["audience"] = str(doc.get("audience") or meta.get("audience") or "")
        meta["theme"] = str(doc.get("theme") or meta.get("theme") or "talent-map")
        meta["research_notes"] = base_notes
        if evidence_meta.get("evidence_pack_id"):
            meta["evidence_pack_id"] = evidence_meta["evidence_pack_id"]
        meta["video_type"] = "presentation"
        meta["content_drafted"] = True
        script = encode_script_bundle(
            {**meta, "full_script": str(doc.get("full_script") or plain)}
        )
        row = await store.update_project(
            user_id,
            project["id"],
            script=script,
            title=str(doc.get("title") or project.get("title") or topic)[:80],
        )
    else:
        row = project

    return web.json_response(
        {
            "ok": bool(out.get("ok")),
            "content": doc,
            "depth": out.get("depth"),
            "applied": bool(apply),
            "project": row,
            "evidence": evidence_meta or None,
            "hint": (
                (
                    "深度文稿已写入"
                    + (
                        f"（已吸收证据 {evidence_meta.get('evidence_count')} 条）"
                        if evidence_meta.get("evidence_count")
                        else ""
                    )
                    + "，请核对后确认 A1"
                )
                if out.get("ok")
                else "已生成但未完全达标，可再点一次深度起草或手工加厚"
            ),
        }
    )


@require_user
async def get_content(request: web.Request) -> web.Response:
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    _s, _u, project = loaded
    data = load_content_json(project["id"])
    return web.json_response(data)


@require_user
async def put_content(request: web.Request) -> web.Response:
    """Save editable slides — writes dist/content.json for instant iframe refresh."""
    loaded = await _load(request)
    if isinstance(loaded, web.Response):
        return loaded
    store, user_id, project = loaded
    plain, meta = _meta(project)
    body = await request.json() if request.can_read_body else {}
    if not isinstance(body, dict):
        return web.json_response({"error": "invalid body"}, status=400)
    chapters = body.get("chapters")
    if not isinstance(chapters, list):
        return web.json_response({"error": "chapters array required"}, status=400)
    path = save_content_json(
        project["id"],
        {
            "title": body.get("title") or project.get("title") or "",
            "theme": body.get("theme") or meta.get("theme") or "",
            "thesis": body.get("thesis") or meta.get("thesis") or "",
            "outline": body.get("outline") if body.get("outline") is not None else meta.get("outline"),
            "full_script": body.get("full_script") if body.get("full_script") is not None else plain,
            "chapters": chapters,
        },
    )
    # Keep outline/script in sync if provided
    if body.get("outline") is not None:
        meta["outline"] = str(body.get("outline") or "")
    if body.get("full_script") is not None:
        plain = str(body.get("full_script") or "")
    meta["video_type"] = "presentation"
    script = encode_script_bundle({**meta, "full_script": plain})
    row = await store.update_project(user_id, project["id"], script=script)
    return web.json_response(
        {
            "ok": True,
            "path": str(path),
            "project": row,
            "content": load_content_json(project["id"]),
        }
    )

def setup_presentation_routes(app: web.Application) -> None:
    app.router.add_get(
        "/api/video/projects/{id}/presentation/meta", presentation_meta
    )
    app.router.add_post(
        "/api/video/projects/{id}/checkpoints/{name}", confirm_checkpoint
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/scaffold", scaffold
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/build", build
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/synthesize-audio", synthesize_audio
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/qc", presentation_qc
    )
    app.router.add_get(
        "/api/video/projects/{id}/presentation/qc", presentation_qc
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/verify", presentation_verify
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/apply-pack", apply_pack
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/draft", draft_content
    )
    app.router.add_get(
        "/api/video/projects/{id}/presentation/content", get_content
    )
    app.router.add_put(
        "/api/video/projects/{id}/presentation/content", put_content
    )
    app.router.add_post(
        "/api/video/projects/{id}/presentation/import", import_video
    )
    app.router.add_post(
        "/api/video/projects/{id}/publish", publish_douyin
    )
    app.router.add_get(
        "/api/video/projects/{id}/presentation/", serve_presentation
    )
    app.router.add_get(
        "/api/video/projects/{id}/presentation", serve_presentation
    )
    app.router.add_get(
        "/api/video/projects/{id}/presentation/{path:.*}", serve_presentation
    )
