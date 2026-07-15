from __future__ import annotations

import os

import pytest

import config
from services import runtime_settings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("abcXYZ_123./:@+-", "abcXYZ_123./:@+-"),
        ("has space", '"has space"'),
        ('quote"and\\slash', '"quote\\"and\\\\slash"'),
    ],
)
def test_format_env_value_quoting_rules(value, expected):
    assert runtime_settings._format_env_value(value) == expected


def test_upsert_local_env_values_creates_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(runtime_settings, "_local_env_path", lambda: env_path)

    returned = runtime_settings.upsert_local_env_values({"A": "1", "B": "two words"})

    assert returned == env_path
    assert env_path.read_text(encoding="utf-8") == 'A=1\nB="two words"\n'


def test_upsert_local_env_values_updates_in_place_and_preserves_other_lines(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("# comment\nA=old\nKEEP=same\n\n", encoding="utf-8")
    monkeypatch.setattr(runtime_settings, "_local_env_path", lambda: env_path)

    runtime_settings.upsert_local_env_values({"A": "new", "C": "see"})

    assert env_path.read_text(encoding="utf-8") == "# comment\nA=new\nKEEP=same\n\nC=see\n"


def test_store_wit_ai_token_updates_runtime_env_and_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setattr(runtime_settings, "_local_env_path", lambda: env_path)
    old_token = config.WIT_AI_TOKEN
    old_auto = config.GOOGLE_CAPTCHA_AUTO_SOLVE
    old_env_token = os.environ.get("WIT_AI_TOKEN")
    old_env_auto = os.environ.get("GOOGLE_CAPTCHA_AUTO_SOLVE")
    try:
        runtime_settings.store_wit_ai_token(" token-123 ")
        assert config.WIT_AI_TOKEN == "token-123"
        assert config.GOOGLE_CAPTCHA_AUTO_SOLVE is True
        assert os.environ["WIT_AI_TOKEN"] == "token-123"
        assert os.environ["GOOGLE_CAPTCHA_AUTO_SOLVE"] == "1"
        assert "WIT_AI_TOKEN=token-123" in env_path.read_text(encoding="utf-8")
    finally:
        config.WIT_AI_TOKEN = old_token
        config.GOOGLE_CAPTCHA_AUTO_SOLVE = old_auto
        _restore_env("WIT_AI_TOKEN", old_env_token)
        _restore_env("GOOGLE_CAPTCHA_AUTO_SOLVE", old_env_auto)


def test_clear_wit_ai_token_clears_runtime_env_and_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("WIT_AI_TOKEN=old\nOTHER=value\n", encoding="utf-8")
    monkeypatch.setattr(runtime_settings, "_local_env_path", lambda: env_path)
    old_token = config.WIT_AI_TOKEN
    old_env_token = os.environ.get("WIT_AI_TOKEN")
    try:
        config.WIT_AI_TOKEN = "old"
        os.environ["WIT_AI_TOKEN"] = "old"
        runtime_settings.clear_wit_ai_token()
        assert config.WIT_AI_TOKEN == ""
        assert os.environ["WIT_AI_TOKEN"] == ""
        assert env_path.read_text(encoding="utf-8") == "WIT_AI_TOKEN=\nOTHER=value\n"
    finally:
        config.WIT_AI_TOKEN = old_token
        _restore_env("WIT_AI_TOKEN", old_env_token)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value
