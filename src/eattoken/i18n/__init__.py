from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Any

_I18N_CACHE: dict[str, dict[str, Any]] = {}


def _load(lang: str) -> dict[str, Any]:
    if lang in _I18N_CACHE:
        return _I18N_CACHE[lang]
    base = Path(__file__).resolve().parent
    path = base / f"{lang}.yaml"
    if not path.exists():
        lang = "en"
        path = base / "en.yaml"
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _I18N_CACHE[lang] = data
    return data


def detect_language() -> str:
    """Detect language from LANG/LC_ALL environment variables."""
    env = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    if env:
        lang = env.split("_")[0].split(".")[0].lower()
        if lang in ("zh", "cn", "chinese"):
            return "zh"
    return "en"


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    """Translate a key into the given language (auto-detect if None)."""
    if lang is None:
        lang = detect_language()
    data = _load(lang)
    text = data.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
