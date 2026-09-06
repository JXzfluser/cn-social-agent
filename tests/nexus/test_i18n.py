"""Locale handling: resolution, fallback, and the served dictionary."""

from __future__ import annotations

import pytest

from cn_social_agent.core import clear
from cn_social_agent.core.i18n import (
    available_locales,
    dictionary,
    output_language_hint,
    t,
    translate,
)
from cn_social_agent.core.tenant import TenantContext, bind


@pytest.fixture(autouse=True)
def _clean():
    yield
    clear()


def test_supported_locales_are_bilingual():
    codes = {item["code"] for item in available_locales()}
    assert codes == {"zh-CN", "en-US"}


def test_translate_switches_language():
    assert translate("nav.tasks", "zh-CN") == "任务"
    assert translate("nav.tasks", "en-US") == "Tasks"


def test_unknown_locale_falls_back():
    assert translate("nav.tasks", "fr-FR") == "任务"
    assert translate("nav.tasks", "en-GB") == "Tasks"


def test_missing_key_returns_the_key():
    assert translate("does.not.exist", "zh-CN") == "does.not.exist"


def test_t_uses_bound_tenant_locale():
    bind(TenantContext(user_id="u", token="user:u", locale="en-US"))
    assert t("app.tagline").startswith("Dispatch")
    clear()
    bind(TenantContext(user_id="u", token="user:u", locale="zh-CN"))
    assert t("app.tagline").startswith("派单")


def test_interpolation():
    bind(TenantContext(user_id="u", token="user:u", locale="zh-CN"))
    assert t("review.failed") == "验收未通过"
    # Unknown placeholders must not raise.
    assert isinstance(translate("common.save", "zh-CN", bogus=1), str)


def test_dictionary_is_complete_for_both_locales():
    zh, en = dictionary("zh-CN"), dictionary("en-US")
    assert set(zh) == set(en), "locales must cover the same keys"
    assert "" not in zh.values()
    assert all(isinstance(v, str) and v for v in en.values())


def test_output_language_hint_tracks_locale():
    assert "Chinese" in output_language_hint("zh-CN")
    assert "English" in output_language_hint("en-US")


def test_locale_normalisation_is_lenient():
    from cn_social_agent.core.tenant import normalize_locale

    for raw, expected in [
        ("zh", "zh-CN"),
        ("en", "en-US"),
        ("zh_CN", "zh-CN"),
        ("EN-us", "en-US"),
        ("zh-Hans-CN", "zh-CN"),
        ("", "zh-CN"),
        (None, "zh-CN"),
        ("klingon", "zh-CN"),
    ]:
        assert normalize_locale(raw) == expected, raw
