"""Tests for the demo verification gate (sandbox + report)."""

from __future__ import annotations

from cn_social_agent.video import sandbox
from cn_social_agent.video.verification import (
    collect_verify_steps,
    normalize_verify,
    verification_report,
)


def test_check_expected_substring_regex_and_empty():
    assert sandbox.check_expected("hello SUCCESS world", "SUCCESS") is True
    assert sandbox.check_expected("nope", "SUCCESS") is False
    assert sandbox.check_expected("exit code 0\n", "re:code\\s+\\d") is True
    assert sandbox.check_expected("anything", "") is True
    assert sandbox.check_expected("x", "re:[") is False  # bad regex → no match


def test_normalize_verify_defaults_and_clamps():
    v = normalize_verify({"command": "  echo hi  ", "expected": "hi", "timeout_s": 9999})
    assert v["command"] == "echo hi"
    assert v["expected"] == "hi"
    assert v["timeout_s"] == 600  # clamped
    assert v["status"] == "pending"


def test_normalize_verify_none_without_command():
    assert normalize_verify({"expected": "hi"}) is None
    assert normalize_verify("nope") is None


def _content_with_demo(verify=None, status=None):
    v = {"command": "echo hi", "expected": "hi"}
    if verify is not None:
        v = verify
    slide = {"title": "run"}
    if verify is not False:
        if status:
            v = {**v, "status": status}
        slide["verify"] = v
    return {
        "title": "t",
        "chapters": [
            {"title": "hook", "role": "hook", "slides": [{"title": "why"}]},
            {"title": "demo", "role": "demo", "slides": [slide]},
        ],
    }


def test_collect_verify_steps_keys():
    steps = collect_verify_steps(_content_with_demo())
    assert len(steps) == 1
    assert steps[0]["key"] == "c1_s0"
    assert steps[0]["command"] == "echo hi"


def test_report_missing_when_demo_has_no_verify():
    rep = verification_report(_content_with_demo(verify=False))
    assert rep["ok"] is False
    assert "demo" in rep["missing_roles"]


def test_report_pending_keeps_gate_open():
    rep = verification_report(_content_with_demo(status="pending"))
    assert rep["ok"] is False
    assert rep["pending"] == 1


def test_report_pass_opens_gate():
    rep = verification_report(_content_with_demo(status="pass"))
    assert rep["ok"] is True
    assert rep["passed"] == 1


def test_report_fail_lists_key():
    rep = verification_report(_content_with_demo(status="fail"))
    assert rep["ok"] is False
    assert rep["failed"] == 1
    assert "c1_s0" in rep["fail_keys"]


import asyncio
from unittest.mock import AsyncMock, patch


def test_run_command_in_docker_pass_via_mock():
    async def _fake_create(*_a, **_k):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"SUCCESS\n", b""))
        return proc

    async def _run():
        with patch(
            "cn_social_agent.video.sandbox.docker_available",
            AsyncMock(return_value=True),
        ), patch(
            "asyncio.create_subprocess_exec",
            side_effect=_fake_create,
        ):
            return await sandbox.run_command_in_docker(
                "echo SUCCESS", expected="SUCCESS"
            )

    res = asyncio.run(_run())
    assert res["status"] == "pass"
    assert res["passed"] is True


def test_run_command_in_docker_unavailable():
    async def _run():
        with patch(
            "cn_social_agent.video.sandbox.docker_available",
            AsyncMock(return_value=False),
        ):
            return await sandbox.run_command_in_docker("echo hi", expected="hi")

    res = asyncio.run(_run())
    assert res["status"] == "unavailable"
    assert res["passed"] is False
