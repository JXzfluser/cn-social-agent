"""Verification gate for presentation demo steps.

A ``demo`` (or ``discovery`` / ``advanced``) slide may declare a ``verify``
block ``{command, expected, image?, timeout_s?, network?}``. This module
normalizes those blocks, runs them in the Docker sandbox, writes the observed
result back onto the slide, and produces a pass/fail report used by the content
quality gate so drafts cannot be marked complete on unverified claims.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator, Optional

from cn_social_agent.video import sandbox
from cn_social_agent.video.presentation import (
    load_content_json,
    presentation_dir,
    save_content_json,
)

# Roles for which a real observable check is expected.
VERIFY_ROLES = {"demo", "discovery", "advanced"}
_VALID_NETWORK = {"none", "bridge", "host"}


def normalize_verify(raw: Any) -> Optional[dict[str, Any]]:
    """Normalize a slide ``verify`` block. Returns None if no command."""
    if not isinstance(raw, dict):
        return None
    command = str(raw.get("command") or "").strip()
    if not command:
        return None
    out: dict[str, Any] = {
        "command": command[:2000],
        "expected": str(raw.get("expected") or "").strip()[:400],
    }
    image = str(raw.get("image") or "").strip()
    if image:
        out["image"] = image[:120]
    try:
        t = int(raw.get("timeout_s") or 0)
    except (TypeError, ValueError):
        t = 0
    if t > 0:
        out["timeout_s"] = min(t, 600)
    net = str(raw.get("network") or "").strip().lower()
    if net in _VALID_NETWORK:
        out["network"] = net
    # Preserve prior run results if present.
    status = str(raw.get("status") or "").strip().lower()
    if status in ("pending", "pass", "fail", "error", "timeout", "unavailable"):
        out["status"] = status
    else:
        out["status"] = "pending"
    for key in ("actual", "reason"):
        if raw.get(key):
            out[key] = str(raw.get(key))[:600]
    if raw.get("exit_code") is not None:
        try:
            out["exit_code"] = int(raw.get("exit_code"))
        except (TypeError, ValueError):
            pass
    if raw.get("ran_at"):
        out["ran_at"] = str(raw.get("ran_at"))[:40]
    if raw.get("logs_ref"):
        out["logs_ref"] = str(raw.get("logs_ref"))[:200]
    return out


def iter_slides(content: dict[str, Any]) -> Iterator[tuple[int, int, dict[str, Any], str]]:
    """Yield (chapter_index, slide_index, slide, role)."""
    chapters = content.get("chapters") if isinstance(content.get("chapters"), list) else []
    for ci, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            continue
        role = str(ch.get("role") or "").strip().lower()
        for si, sl in enumerate(ch.get("slides") or []):
            if isinstance(sl, dict):
                yield ci, si, sl, role


def slide_key(ci: int, si: int) -> str:
    return f"c{ci}_s{si}"


def collect_verify_steps(content: dict[str, Any]) -> list[dict[str, Any]]:
    """Build runnable steps from slides that declare a verify command."""
    steps: list[dict[str, Any]] = []
    for ci, si, sl, _role in iter_slides(content):
        v = normalize_verify(sl.get("verify"))
        if v is None:
            continue
        step = {"key": slide_key(ci, si), "command": v["command"], "expected": v.get("expected", "")}
        for opt in ("image", "timeout_s", "network"):
            if v.get(opt) is not None:
                step[opt] = v[opt]
        steps.append(step)
    return steps


def verification_report(content: dict[str, Any]) -> dict[str, Any]:
    """Summarize declared/passed verify steps and whether the gate passes.

    Gate rule (content-time): every chapter whose role is in VERIFY_ROLES and
    that exists in the draft must declare at least one verify block, and all
    declared verify blocks that have been run must be ``pass``. Unrun (pending)
    blocks keep the gate open (not yet verified).
    """
    roles_present: set[str] = set()
    roles_with_declared: set[str] = set()
    declared = 0
    passed = 0
    failed = 0
    pending = 0
    unavailable = 0
    fail_keys: list[str] = []

    for ci, si, sl, role in iter_slides(content):
        if role in VERIFY_ROLES:
            roles_present.add(role)
        v = normalize_verify(sl.get("verify"))
        if v is None:
            continue
        declared += 1
        if role in VERIFY_ROLES:
            roles_with_declared.add(role)
        status = v.get("status", "pending")
        if status == "pass":
            passed += 1
        elif status == "pending":
            pending += 1
        elif status == "unavailable":
            unavailable += 1
        else:
            failed += 1
            fail_keys.append(slide_key(ci, si))

    missing_roles = sorted(roles_present - roles_with_declared)
    all_declared_run = (declared > 0) and (pending == 0)
    ok = (
        not missing_roles
        and declared > 0
        and failed == 0
        and pending == 0
        and unavailable == 0
    )
    return {
        "ok": ok,
        "declared": declared,
        "passed": passed,
        "failed": failed,
        "pending": pending,
        "unavailable": unavailable,
        "all_declared_run": all_declared_run,
        "roles_present": sorted(roles_present),
        "missing_roles": missing_roles,
        "fail_keys": fail_keys,
    }


def _verify_log_dir(project_id: str) -> Path:
    d = presentation_dir(project_id) / "verify"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_log(project_id: str, key: str, res: dict[str, Any]) -> str:
    d = _verify_log_dir(project_id)
    path = d / f"{key}.log"
    body = (
        f"$ {res.get('command', '')}\n"
        f"# status={res.get('status')} exit={res.get('exit_code')}\n"
        f"--- stdout ---\n{res.get('stdout', '')}\n"
        f"--- stderr ---\n{res.get('stderr', '')}\n"
    )
    try:
        path.write_text(body, encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""
    return f"verify/{key}.log"


def _apply_result(slide: dict[str, Any], res: dict[str, Any], logs_ref: str) -> None:
    v = normalize_verify(slide.get("verify")) or {}
    v["status"] = res.get("status", "error")
    v["exit_code"] = res.get("exit_code")
    v["reason"] = res.get("reason", "")
    v["actual"] = (res.get("stdout") or res.get("stderr") or "")[:600]
    v["ran_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    if logs_ref:
        v["logs_ref"] = logs_ref
    slide["verify"] = v


async def run_verification(
    project_id: str, *, meta: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Run all declared verify steps in the sandbox and persist results.

    Returns a dict with ``report`` (post-run summary), ``results`` (per step),
    and ``hint`` (中文摘要). Content.json is updated in place with statuses.
    """
    content = load_content_json(project_id)
    steps = collect_verify_steps(content)
    if not steps:
        report = verification_report(content)
        return {
            "ran": 0,
            "report": report,
            "results": [],
            "docker": await sandbox.docker_available(),
            "hint": "无 demo 验证步（未声明 verify.command）",
        }

    docker_ok = await sandbox.docker_available()
    results = await sandbox.run_steps(steps)

    by_key = {r.get("key"): r for r in results}
    for ci, si, sl, _role in iter_slides(content):
        key = slide_key(ci, si)
        res = by_key.get(key)
        if not res:
            continue
        res_with_cmd = {**res, "command": next((s["command"] for s in steps if s["key"] == key), "")}
        logs_ref = _write_log(project_id, key, res_with_cmd)
        _apply_result(sl, res, logs_ref)

    save_content_json(project_id, content)
    report = verification_report(content)

    n_pass = sum(1 for r in results if r.get("status") == "pass")
    n_fail = len(results) - n_pass
    if not docker_ok:
        hint = "Docker 不可用：验证跳过（unavailable），请启动 Docker 后重试"
    elif report.get("ok"):
        hint = f"验证通过：{n_pass}/{len(results)} 步命中 expected"
    else:
        parts = [f"{n_pass}/{len(results)} 通过"]
        if n_fail:
            parts.append(f"{n_fail} 失败")
        if report.get("missing_roles"):
            parts.append("缺声明：" + "、".join(report["missing_roles"]))
        hint = "验证未通过：" + "，".join(parts)

    return {
        "ran": len(results),
        "report": report,
        "results": results,
        "docker": docker_ok,
        "hint": hint,
    }
