"""Docker-backed verification sandbox for presentation demo steps.

Runs a demo step's shell command inside a throwaway container, captures
stdout/stderr/exit code, and checks the observed output against an expected
substring or ``re:`` regex. Degrades gracefully to status ``unavailable`` when
Docker is not reachable so callers can gate content without crashing.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from typing import Any, Optional

# Conservative defaults — demo steps should be quick, self-contained checks.
DEFAULT_IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT_S = 60
DEFAULT_NETWORK = "none"  # no network unless a step explicitly opts in
_MAX_OUTPUT_CHARS = 4000

_docker_cache: dict[str, Any] = {}


def check_expected(output: str, expected: str) -> bool:
    """Match observed output against expected.

    - ``re:PATTERN`` → regex search (multiline, dotall)
    - otherwise → case-sensitive substring match
    - empty expected → any non-error output counts (caller decides via exit code)
    """
    exp = (expected or "").strip()
    out = output or ""
    if not exp:
        return True
    if exp.startswith("re:"):
        pattern = exp[3:]
        try:
            return re.search(pattern, out, re.MULTILINE | re.DOTALL) is not None
        except re.error:
            return False
    return exp in out


def _clip_output(text: str) -> str:
    t = text or ""
    if len(t) <= _MAX_OUTPUT_CHARS:
        return t
    return t[-_MAX_OUTPUT_CHARS:]


async def docker_available(*, force: bool = False) -> bool:
    """Best-effort probe: is a Docker daemon reachable? Cached for 60s."""
    now = time.time()
    if not force and _docker_cache.get("at", 0) + 60 > now:
        return bool(_docker_cache.get("ok"))
    ok = False
    if shutil.which("docker"):
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "version",
                "--format",
                "{{.Server.Version}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, _err = await asyncio.wait_for(proc.communicate(), timeout=8)
            except asyncio.TimeoutError:
                proc.kill()
                out = b""
            ok = proc.returncode == 0 and bool((out or b"").strip())
        except Exception:  # noqa: BLE001
            ok = False
    _docker_cache["at"] = now
    _docker_cache["ok"] = ok
    return ok


def _docker_run_argv(
    command: str,
    *,
    image: str,
    workdir: str,
    network: str,
    memory: str,
    cpus: str,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        network or DEFAULT_NETWORK,
        "--memory",
        memory,
        "--cpus",
        cpus,
        "--pids-limit",
        "256",
        "-w",
        workdir,
        image,
        "sh",
        "-lc",
        command,
    ]


async def run_command_in_docker(
    command: str,
    *,
    image: str = DEFAULT_IMAGE,
    expected: str = "",
    timeout_s: int = DEFAULT_TIMEOUT_S,
    network: str = DEFAULT_NETWORK,
    workdir: str = "/work",
    memory: str = "512m",
    cpus: str = "1.0",
) -> dict[str, Any]:
    """Run one command in a throwaway container; return a structured result.

    Status: pass | fail | error | timeout | unavailable
    """
    command = (command or "").strip()
    if not command:
        return {
            "status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "passed": False,
            "reason": "空命令",
        }

    if not await docker_available():
        return {
            "status": "unavailable",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "passed": False,
            "reason": "Docker 不可用（未启动或无权限）",
        }

    argv = _docker_run_argv(
        command,
        image=image or DEFAULT_IMAGE,
        workdir=workdir,
        network=network or DEFAULT_NETWORK,
        memory=memory,
        cpus=cpus,
    )
    started = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc)[:500],
            "passed": False,
            "reason": f"启动容器失败：{type(exc).__name__}",
        }

    timed_out = False
    try:
        out_b, err_b = await asyncio.wait_for(
            proc.communicate(), timeout=max(1, int(timeout_s or DEFAULT_TIMEOUT_S))
        )
    except asyncio.TimeoutError:
        timed_out = True
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        out_b, err_b = b"", b""

    stdout = _clip_output((out_b or b"").decode("utf-8", "replace"))
    stderr = _clip_output((err_b or b"").decode("utf-8", "replace"))
    elapsed_ms = int((time.time() - started) * 1000)

    if timed_out:
        return {
            "status": "timeout",
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "passed": False,
            "reason": f"超时（>{timeout_s}s）",
            "elapsed_ms": elapsed_ms,
        }

    exit_code = proc.returncode
    combined = stdout + ("\n" + stderr if stderr else "")
    expected_ok = check_expected(combined, expected)
    passed = exit_code == 0 and expected_ok
    if passed:
        status = "pass"
        reason = ""
    elif exit_code != 0:
        status = "fail"
        reason = f"退出码 {exit_code}"
    else:
        status = "fail"
        reason = "输出未命中 expected"

    return {
        "status": status,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "passed": passed,
        "expected_ok": expected_ok,
        "reason": reason,
        "elapsed_ms": elapsed_ms,
    }


async def run_steps(
    steps: list[dict[str, Any]],
    *,
    default_image: str = DEFAULT_IMAGE,
    default_timeout_s: int = DEFAULT_TIMEOUT_S,
) -> list[dict[str, Any]]:
    """Run a list of {command, expected, image?, timeout_s?, network?} steps.

    Steps run sequentially (a demo is a narrative order). Returns per-step
    results carrying the original key so callers can map back onto slides.
    """
    results: list[dict[str, Any]] = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        res = await run_command_in_docker(
            str(step.get("command") or ""),
            image=str(step.get("image") or default_image) or default_image,
            expected=str(step.get("expected") or ""),
            timeout_s=int(step.get("timeout_s") or default_timeout_s),
            network=str(step.get("network") or DEFAULT_NETWORK) or DEFAULT_NETWORK,
        )
        res["key"] = step.get("key")
        results.append(res)
    return results
