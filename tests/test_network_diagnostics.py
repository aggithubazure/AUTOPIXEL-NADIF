from __future__ import annotations

import pytest

from services import network_diagnostics


def test_normalize_http_proxy_returns_none_for_direct():
    assert network_diagnostics._normalize_http_proxy(None) is None
    assert network_diagnostics._normalize_http_proxy("") is None


def test_normalize_http_proxy_normalizes_http_url():
    assert network_diagnostics._normalize_http_proxy("127.0.0.1:8080") == "http://127.0.0.1:8080"


@pytest.mark.parametrize("proxy", ["socks5://127.0.0.1:1080", "socks5h://127.0.0.1:1080"])
def test_normalize_http_proxy_rejects_socks(proxy):
    with pytest.raises(RuntimeError, match="SOCKS proxy probing"):
        network_diagnostics._normalize_http_proxy(proxy)


def test_build_proxy_handler_direct_has_empty_proxies():
    handler = network_diagnostics._build_proxy_handler(None)
    assert handler.proxies == {}


def test_build_proxy_handler_rejects_socks():
    with pytest.raises(RuntimeError, match="SOCKS proxy probing"):
        network_diagnostics._build_proxy_handler("socks5://127.0.0.1:1080")


def test_format_connection_identity_includes_available_fields():
    text = network_diagnostics.format_connection_identity({
        "proxy": "http://user:****@proxy.test:8080",
        "proxy_host": "proxy.test:8080",
        "ip": "203.0.113.10",
        "country": "Indonesia",
        "country_code": "ID",
        "continent": "Asia",
        "region": "Jakarta",
        "city": "Jakarta",
        "postal": "12345",
        "timezone": "Asia/Jakarta",
        "timezone_abbr": "WIB",
        "timezone_utc": "+07:00",
        "latitude": "-6.2",
        "longitude": "106.8",
        "org": "Example Org",
        "isp": "Example ISP",
        "asn": "64500",
        "domain": "example.net",
    }, title="Title")
    assert "Title" in text
    assert "🌐 Proxy: http://user:****@proxy.test:8080" in text
    assert "🔌 Proxy host: proxy.test:8080" in text
    assert "🧷 Public IP: 203.0.113.10" in text
    assert "🏳️ Country: Indonesia (ID)" in text
    assert "🕒 Timezone: Asia/Jakarta | WIB | +07:00" in text
    assert "🧭 Coordinates: -6.2, 106.8" in text


@pytest.mark.parametrize(
    ("exc", "fragment"),
    [
        (RuntimeError("407 Proxy Authentication Required"), "Proxy authentication failed (407)"),
        (RuntimeError("proxy authentication required"), "Proxy authentication failed (407)"),
        (RuntimeError("bad_endpoint policy_20130"), "provider blocked this destination by policy"),
        (RuntimeError("plain failure"), "Probe: plain failure"),
    ],
)
def test_format_probe_error_maps_known_messages(exc, fragment):
    formatted = network_diagnostics._format_probe_error("Probe", exc)
    assert isinstance(formatted, RuntimeError)
    assert fragment in str(formatted)
