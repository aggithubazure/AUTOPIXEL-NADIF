from __future__ import annotations

import pytest

import config
from core.proxy_manager import (
    ProxyManager,
    mask_proxy_url,
    normalize_proxy_url,
    parse_proxy_parts,
    resolve_runtime_proxy_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("socks5://127.0.0.1:1080", "socks5://127.0.0.1:1080"),
        ("user:pass@127.0.0.1:8080", "http://user:pass@127.0.0.1:8080"),
        ("127.0.0.1:8080:user:pass", "http://user:pass@127.0.0.1:8080"),
        ("host.test:8080:user name:pass word", "http://user%20name:pass%20word@host.test:8080"),
    ],
)
def test_normalize_proxy_url_canonicalizes_supported_formats(raw, expected):
    assert normalize_proxy_url(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "# comment"])
def test_normalize_proxy_url_ignores_empty_and_comments(raw):
    assert normalize_proxy_url(raw) == ""


@pytest.mark.parametrize("raw", ["ftp://127.0.0.1:21", "ssh://host:22"])
def test_normalize_proxy_url_rejects_unsupported_schemes(raw):
    with pytest.raises(ValueError, match="Unsupported proxy scheme"):
        normalize_proxy_url(raw)


@pytest.mark.parametrize("raw", ["localhost", "http://localhost", "http://:8080"])
def test_normalize_proxy_url_rejects_missing_host_or_port(raw):
    with pytest.raises(ValueError, match="Invalid proxy format"):
        normalize_proxy_url(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "direct"),
        ("127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("user:pass@127.0.0.1:8080", "http://user:****@127.0.0.1:8080"),
        ("bad", "invalid"),
    ],
)
def test_mask_proxy_url_current_outputs(raw, expected):
    assert mask_proxy_url(raw) == expected


def test_parse_proxy_parts_unquotes_credentials():
    assert parse_proxy_parts("http://user%20name:p%40ss@host.test:8080") == {
        "scheme": "http",
        "host": "host.test",
        "port": 8080,
        "username": "user name",
        "password": "p@ss",
    }


@pytest.mark.parametrize(
    ("proxy_url", "expected"),
    [
        (None, None),
        ("", ""),
        ("127.0.0.1:8080", "http://127.0.0.1:8080"),
        ("bad", "bad"),
    ],
)
def test_resolve_runtime_proxy_url_normalizes_without_using_token(proxy_url, expected):
    assert resolve_runtime_proxy_url(proxy_url, proxy_session_token="Sticky123") == expected


@pytest.fixture
def proxy_file(tmp_path):
    path = tmp_path / "proxies.txt"
    path.write_text(
        "\n".join([
            "10.0.0.2:8002",
            "10.0.0.1:8001",
            "# skipped",
            "10.0.0.3:8003:user:pass",
        ]) + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def proxy_config(monkeypatch):
    monkeypatch.setattr(config, "PROXY_ENABLED", True)
    monkeypatch.setattr(config, "PROXY_FAILURE_COOLDOWN_SECONDS", 100)
    monkeypatch.setattr(config, "PROXY_QUARANTINE_SECONDS", 200)
    monkeypatch.setattr(config, "PROXY_QUARANTINE_THRESHOLD", 2)


def test_proxy_manager_has_pool_true_and_false(tmp_path, proxy_file, proxy_config, monkeypatch):
    assert ProxyManager(str(proxy_file)).has_pool() is True
    missing = tmp_path / "missing.txt"
    assert ProxyManager(str(missing)).has_pool() is False
    monkeypatch.setattr(config, "PROXY_ENABLED", False)
    assert ProxyManager(str(proxy_file)).has_pool() is False


def test_proxy_manager_round_robins_over_sorted_healthy_candidates(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    assert [manager.get_proxy() for _ in range(4)] == [
        "http://10.0.0.1:8001",
        "http://10.0.0.2:8002",
        "http://user:pass@10.0.0.3:8003",
        "http://10.0.0.1:8001",
    ]


def test_proxy_manager_preferred_proxy_wins_when_healthy(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    assert manager.get_proxy(preferred="10.0.0.2:8002") == "http://10.0.0.2:8002"


def test_proxy_manager_get_proxy_excludes_urls(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    excluded = {"http://10.0.0.1:8001", "http://10.0.0.2:8002"}
    assert manager.get_proxy(excluded=excluded) == "http://user:pass@10.0.0.3:8003"


def test_proxy_manager_mark_failed_cools_down_then_quarantines(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    proxy = "10.0.0.1:8001"
    manager.mark_failed(proxy, code="auth")
    stats = manager.stats()
    assert stats == {"total": 3, "available": 2, "cooling_down": 1, "quarantined": 0}
    status = manager._proxies["http://10.0.0.1:8001"]
    assert status.fail_count == 1
    assert status.last_error_code == "auth"

    manager.mark_failed(proxy, code="timeout")
    stats = manager.stats()
    assert stats == {"total": 3, "available": 2, "cooling_down": 0, "quarantined": 1}
    assert status.fail_count == 2
    assert status.last_error_code == "timeout"
    assert status.quarantined_until > manager._now()


def test_proxy_manager_mark_success_resets_failure_state(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    proxy = "10.0.0.1:8001"
    manager.mark_failed(proxy)
    manager.mark_success(proxy, latency_ms=12.5)
    status = manager._proxies["http://10.0.0.1:8001"]
    assert status.fail_count == 0
    assert status.cooldown_until == 0.0
    assert status.quarantined_until == 0.0
    assert status.success_count == 1
    assert status.last_latency_ms == 12.5
    assert manager.stats() == {"total": 3, "available": 3, "cooling_down": 0, "quarantined": 0}


def test_proxy_manager_falls_back_to_cooling_down_candidates(proxy_file, proxy_config):
    manager = ProxyManager(str(proxy_file))
    for proxy in list(manager._proxies):
        manager.mark_failed(proxy)
    # characterization: locks current behavior that cooling-down proxies are reused when all are cooling down.
    assert manager.get_proxy() in set(manager._proxies)
