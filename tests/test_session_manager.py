from __future__ import annotations

import time

import pytest

import config
from core import session_manager


@pytest.fixture(autouse=True)
def isolated_session_store():
    original = dict(session_manager.SESSION_STORE)
    session_manager.SESSION_STORE.clear()
    yield
    session_manager.SESSION_STORE.clear()
    session_manager.SESSION_STORE.update(original)


def test_secure_wipe_zero_fills_bytearray_in_place():
    data = bytearray(b"secret")
    original_id = id(data)
    session_manager.secure_wipe(data)
    assert id(data) == original_id
    assert data == bytearray(b"\x00" * 6)


def test_is_session_expired_uses_configured_ttl(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 5)
    assert session_manager.is_session_expired({"created_at": time.time() - 6}) is True
    assert session_manager.is_session_expired({"created_at": time.time()}) is False


def test_is_session_expired_without_created_at_is_false():
    assert session_manager.is_session_expired({}) is False


def test_ensure_proxy_session_token_is_stable_alnum_and_limited():
    session = {}
    token = session_manager.ensure_proxy_session_token(session, seed="ABC-123_xyz!longer-than-24-chars")
    assert token == "abc123xyzlongerthan24cha"
    assert token.isalnum()
    assert len(token) <= 24
    assert session_manager.ensure_proxy_session_token(session, seed="different") == token


def test_ensure_proxy_session_token_uses_existing_stripped_value():
    session = {"_proxy_session_token": " ExistingToken "}
    # characterization: locks current behavior returning existing token without writing stripped value back.
    assert session_manager.ensure_proxy_session_token(session) == "ExistingToken"
    assert session["_proxy_session_token"] == " ExistingToken "


def test_get_session_creates_and_reuses_session():
    first = session_manager.get_session(123)
    first["email"] = bytearray(b"a@example.com")
    assert session_manager.get_session(123) is first
    assert session_manager.SESSION_STORE[123] is first


def test_get_session_clears_expired_session(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 1)
    old_email = bytearray(b"old@example.com")
    old_password = bytearray(b"old-password")
    session_manager.SESSION_STORE[5] = {
        "created_at": time.time() - 10,
        "email": old_email,
        "password": old_password,
    }
    new_session = session_manager.get_session(5)
    assert new_session == {}
    assert old_email == bytearray(len(old_email))
    assert old_password == bytearray(len(old_password))


def test_clear_session_secure_wipes_credentials_and_quits_driver():
    class Driver:
        def __init__(self):
            self.quit_called = False

        def quit(self):
            self.quit_called = True

    email = bytearray(b"me@example.com")
    password = bytearray(b"password")
    driver = Driver()
    session = {"email": email, "password": password, "_driver": driver, "other": "value"}
    session_manager.SESSION_STORE[77] = session

    session_manager.clear_session(77)

    assert 77 not in session_manager.SESSION_STORE
    assert email == bytearray(len(email))
    assert password == bytearray(len(password))
    assert driver.quit_called is True
    assert session == {}


def test_clear_session_missing_chat_is_noop():
    session_manager.clear_session(999)
    assert session_manager.SESSION_STORE == {}


def test_purge_expired_sessions_only_removes_expired(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", 5)
    expired_password = bytearray(b"expired")
    session_manager.SESSION_STORE[1] = {"created_at": time.time() - 10, "password": expired_password}
    session_manager.SESSION_STORE[2] = {"created_at": time.time(), "password": bytearray(b"fresh")}
    session_manager.SESSION_STORE[3] = {"password": bytearray(b"no-created")}

    assert session_manager.purge_expired_sessions() == 1
    assert set(session_manager.SESSION_STORE) == {2, 3}
    assert expired_password == bytearray(len(expired_password))
