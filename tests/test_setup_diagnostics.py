from __future__ import annotations

from services import setup_diagnostics
import config


def _checks_by_name(diagnostics):
    return {item["name"]: item["status"] for item in diagnostics["checks"]}


def test_collect_setup_diagnostics_summary_fail_precedence(tmp_path, monkeypatch):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("127.0.0.1:8080\ninvalid\n", encoding="utf-8")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "PROXY_ENABLED", True)
    monkeypatch.setattr(config, "PROXY_FILE_PATH", str(proxy_file))
    monkeypatch.setattr(config, "BOT_HEADER_MEDIA_URL", "https://example.test/header.png")
    monkeypatch.setattr(setup_diagnostics, "_detect_chrome_binary", lambda: "")

    diagnostics = setup_diagnostics.collect_setup_diagnostics()

    checks = _checks_by_name(diagnostics)
    assert diagnostics["summary"] == "fail"
    assert checks["telegram_token"] == "fail"
    assert checks["chrome_binary"] == "fail"
    assert checks["proxy_pool"] == "warn"
    assert diagnostics["proxy_pool"]["valid_entries"] == 1
    assert diagnostics["proxy_pool"]["invalid_entries"] == 1


def test_collect_setup_diagnostics_summary_warn_when_no_failures(tmp_path, monkeypatch):
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text("127.0.0.1:8080\n", encoding="utf-8")
    missing_media = tmp_path / "missing.png"
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "PROXY_ENABLED", True)
    monkeypatch.setattr(config, "PROXY_FILE_PATH", str(proxy_file))
    monkeypatch.setattr(config, "BOT_HEADER_MEDIA_URL", str(missing_media))
    monkeypatch.setattr(setup_diagnostics, "_detect_chrome_binary", lambda: "chrome.exe")

    diagnostics = setup_diagnostics.collect_setup_diagnostics()

    checks = _checks_by_name(diagnostics)
    assert diagnostics["summary"] == "warn"
    assert checks["telegram_token"] == "ok"
    assert checks["chrome_binary"] == "ok"
    assert checks["header_media"] == "warn"
    assert checks["proxy_pool"] == "ok"


def test_collect_setup_diagnostics_summary_ok(tmp_path, monkeypatch):
    proxy_file = tmp_path / "proxies.txt"
    media_file = tmp_path / "header.png"
    fake_env = tmp_path / "config.py"
    proxy_file.write_text("127.0.0.1:8080\n", encoding="utf-8")
    media_file.write_text("x", encoding="utf-8")
    fake_env.write_text("# config placeholder", encoding="utf-8")
    (tmp_path / ".env").write_text("X=1\n", encoding="utf-8")
    monkeypatch.setattr(config, "__file__", str(fake_env))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "PROXY_ENABLED", True)
    monkeypatch.setattr(config, "PROXY_FILE_PATH", str(proxy_file))
    monkeypatch.setattr(config, "BOT_HEADER_MEDIA_URL", str(media_file))
    monkeypatch.setattr(setup_diagnostics, "_detect_chrome_binary", lambda: "chrome.exe")

    diagnostics = setup_diagnostics.collect_setup_diagnostics()

    assert diagnostics["summary"] == "ok"
    assert all(item["status"] == "ok" for item in diagnostics["checks"])
    assert diagnostics["header_media"]["mode"] == "local"
    assert diagnostics["proxy_pool"]["readable"] is True


def test_collect_setup_diagnostics_proxy_disabled_is_ok(tmp_path, monkeypatch):
    proxy_file = tmp_path / "missing.txt"
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "PROXY_ENABLED", False)
    monkeypatch.setattr(config, "PROXY_FILE_PATH", str(proxy_file))
    monkeypatch.setattr(config, "BOT_HEADER_MEDIA_URL", "https://example.test/header.png")
    monkeypatch.setattr(setup_diagnostics, "_detect_chrome_binary", lambda: "chrome.exe")

    diagnostics = setup_diagnostics.collect_setup_diagnostics()

    assert _checks_by_name(diagnostics)["proxy_pool"] == "ok"
    assert diagnostics["proxy_pool"]["enabled"] is False
