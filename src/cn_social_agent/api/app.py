"""Workbench aiohttp application."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

from cn_social_agent.api.auth import setup_auth_routes
from cn_social_agent.api.chat import setup_chat_routes
from cn_social_agent.api.deps import AppState
from cn_social_agent.api.health import setup_health_routes
from cn_social_agent.api.hotspots_routes import setup_hotspots_routes
from cn_social_agent.api.media import setup_media_routes
from cn_social_agent.api.nexus_routes import setup_nexus_routes
from cn_social_agent.api.sessions import setup_session_routes
from cn_social_agent.api.settings_routes import setup_settings_routes
from cn_social_agent.api.skills_routes import setup_skills_routes
from cn_social_agent.api.tools_routes import setup_tools_routes
from cn_social_agent.api.card_routes import setup_card_routes
from cn_social_agent.api.content_project_routes import setup_content_project_routes
from cn_social_agent.api.learn_routes import setup_learn_routes
from cn_social_agent.api.connector_routes import setup_connector_routes
from cn_social_agent.api.automation_routes import setup_automation_routes
from cn_social_agent.api.workflow_routes import setup_workflow_routes
from cn_social_agent.api.canvas_routes import setup_canvas_routes
from cn_social_agent.api.assets_routes import setup_assets_routes
from cn_social_agent.api.topic_hub_routes import setup_topic_hub_routes
from cn_social_agent.api.oauth_routes import setup_oauth_routes
from cn_social_agent.api.packs_routes import setup_packs_routes
from cn_social_agent.api.usage_routes import setup_usage_routes
from cn_social_agent.api.video_routes import setup_video_routes
from cn_social_agent.api.idea_routes import routes as idea_routes
from cn_social_agent.idea_engine.scheduler import start_scheduler, stop_scheduler, set_app

WORKBENCH_DIR = Path(__file__).resolve().parent.parent / "workbench"
WORKFLOW_DIR = Path(__file__).resolve().parent.parent / "workflow"
NEXUS_DIR = Path(__file__).resolve().parent.parent / "workbench" / "nexus"


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(
        WORKBENCH_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )


async def favicon(_request: web.Request) -> web.FileResponse:
    path = WORKBENCH_DIR / "assets" / "favicon.ico"
    if not path.exists():
        path = WORKBENCH_DIR / "assets" / "favicon.svg"
    return web.FileResponse(path)


async def on_startup(app: web.Application) -> None:
    state: AppState = app["state"]
    await state.startup()


async def on_cleanup(app: web.Application) -> None:
    state: AppState = app["state"]
    await state.shutdown()


def create_app() -> web.Application:
    app = web.Application(client_max_size=20 * 1024 * 1024)
    app["state"] = AppState()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    setup_health_routes(app)
    setup_auth_routes(app)
    setup_session_routes(app)
    setup_chat_routes(app)
    setup_skills_routes(app)
    setup_tools_routes(app)
    setup_media_routes(app)
    setup_video_routes(app)
    setup_card_routes(app)
    setup_content_project_routes(app)
    setup_learn_routes(app)
    setup_connector_routes(app)
    setup_automation_routes(app)
    setup_workflow_routes(app)
    setup_canvas_routes(app)
    setup_assets_routes(app)
    setup_topic_hub_routes(app)
    setup_oauth_routes(app)
    setup_hotspots_routes(app)
    setup_settings_routes(app)
    setup_usage_routes(app)
    setup_packs_routes(app)
    setup_nexus_routes(app)
    from cn_social_agent.api.library_routes import setup_library_routes
    from cn_social_agent.api.export_routes import setup_export_routes
    from cn_social_agent.api.im_routes import setup_im_routes

    setup_library_routes(app)
    setup_export_routes(app)
    setup_im_routes(app)
    app.router.add_routes(idea_routes)

    app.router.add_get("/", index)
    app.router.add_get("/favicon.ico", favicon)
    if WORKBENCH_DIR.exists():
        app.router.add_static("/static/", WORKBENCH_DIR, show_index=False)
    if WORKFLOW_DIR.exists():
        app.router.add_static("/workflow/", WORKFLOW_DIR, show_index=False)
    if NEXUS_DIR.exists():
        # Register the index BEFORE add_static, otherwise "/nexus/" falls into
        # the static handler which returns 403 with show_index=False.
        app.router.add_get("/nexus", nexus_index)
        app.router.add_get("/nexus/", nexus_index)
        app.router.add_static("/nexus/", NEXUS_DIR, show_index=False)

    return app


async def nexus_index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(NEXUS_DIR / "index.html", headers={"Cache-Control": "no-store"})
