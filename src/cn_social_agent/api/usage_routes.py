"""Internal usage summary API (no billing)."""

from __future__ import annotations

from aiohttp import web

from cn_social_agent.api.auth import require_user
from cn_social_agent.usage.meter import format_weekly_report, weekly_summary


@require_user
async def usage_summary(request: web.Request) -> web.Response:
    try:
        days = int(request.rel_url.query.get("days") or "7")
    except ValueError:
        days = 7
    days = max(1, min(days, 90))
    summary = weekly_summary(days=days)
    fmt = (request.rel_url.query.get("format") or "json").strip().lower()
    if fmt in ("text", "md", "markdown"):
        return web.Response(
            text=format_weekly_report(summary),
            content_type="text/plain; charset=utf-8",
        )
    return web.json_response(summary)


def setup_usage_routes(app: web.Application) -> None:
    app.router.add_get("/api/usage/summary", usage_summary)
