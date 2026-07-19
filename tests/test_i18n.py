import pytest
from eattoken.i18n import t, detect_language, _load


def test_i18n_default_english():
    text = t("app_title")
    assert text == "EatToken"


def test_i18n_chinese():
    text = t("app_title", lang="zh")
    assert text == "EatToken"


def test_i18n_missing_key_returns_key():
    text = t("nonexistent_key_xyz")
    assert text == "nonexistent_key_xyz"


def test_i18n_format_args():
    text = t("placeholder_target_tokens", lang="en")
    assert "Leave empty" in text
