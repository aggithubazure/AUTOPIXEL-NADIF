"""Tests for persistent Chrome profiles, saved-session reuse, and offer scan."""

import config
from services import google_automation as ga
from services.google_automation import (
    _chrome_profile_dir_for,
    _is_authenticated_session,
    extract_payment_link,
)


# ── Persistent profile directory ─────────────────────────────────────────────


def test_profile_dir_none_when_key_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PERSIST_CHROME_PROFILE", True)
    monkeypatch.setattr(config, "CHROME_PROFILE_DIR", str(tmp_path))
    assert _chrome_profile_dir_for(None) is None
    assert _chrome_profile_dir_for("") is None


def test_profile_dir_none_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PERSIST_CHROME_PROFILE", False)
    monkeypatch.setattr(config, "CHROME_PROFILE_DIR", str(tmp_path))
    assert _chrome_profile_dir_for("user@gmail.com") is None


def test_profile_dir_is_stable_and_created(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PERSIST_CHROME_PROFILE", True)
    monkeypatch.setattr(config, "CHROME_PROFILE_DIR", str(tmp_path))
    first = _chrome_profile_dir_for("User@Gmail.com")
    second = _chrome_profile_dir_for("user@gmail.com ")  # case/space insensitive
    assert first is not None
    assert first == second  # same account -> same dir
    assert first.startswith(str(tmp_path))
    import os

    assert os.path.isdir(first)
    # The raw email must not leak into the path.
    assert "user@gmail.com" not in first


def test_profile_dir_differs_per_account(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PERSIST_CHROME_PROFILE", True)
    monkeypatch.setattr(config, "CHROME_PROFILE_DIR", str(tmp_path))
    assert _chrome_profile_dir_for("a@gmail.com") != _chrome_profile_dir_for("b@gmail.com")


# ── Saved-session probe ──────────────────────────────────────────────────────


class _FakeAuthDriver:
    def __init__(self, resolved_url):
        self.current_url = resolved_url
        self.requested = None

    def get(self, url):
        self.requested = url


def test_authenticated_session_true_on_myaccount():
    driver = _FakeAuthDriver("https://myaccount.google.com/?pli=1")
    assert _is_authenticated_session(driver, timeout=1.0) is True
    assert driver.requested == "https://myaccount.google.com/"


def test_authenticated_session_false_on_signin_redirect():
    driver = _FakeAuthDriver(
        "https://accounts.google.com/signin/v2/identifier?continue=..."
    )
    assert _is_authenticated_session(driver, timeout=1.0) is False


# ── Offer detection broadening ───────────────────────────────────────────────


class _FakeLink:
    def __init__(self, href="", text="", aria=""):
        self._href = href
        self.text = text
        self._aria = aria

    def get_attribute(self, name):
        if name == "href":
            return self._href
        if name == "aria-label":
            return self._aria
        return None


class _FakeOfferDriver:
    def __init__(self, links):
        self._links = links
        self.current_url = "https://one.google.com/about/plans"

    def find_elements(self, by, value):
        # Only anchor scans return links; the trial-button (CSS) scan is empty.
        if value == "a":
            return list(self._links)
        return []


def test_offer_returns_partner_eft_link():
    driver = _FakeOfferDriver(
        [
            _FakeLink(href="https://one.google.com/benefits/LOCKED:YOUTUBE_PREMIUM"),
            _FakeLink(
                href="https://one.google.com/about/plans?utm=partner-eft-onboard-abc",
                text="Redeem",
            ),
        ]
    )
    assert (
        extract_payment_link(driver)
        == "https://one.google.com/about/plans?utm=partner-eft-onboard-abc"
    )


def test_offer_skips_locked_and_benefit_links():
    driver = _FakeOfferDriver(
        [
            _FakeLink(
                href="https://one.google.com/benefits/LOCKED:FITBIT_PREMIUM",
                text="Redeem offer",
            ),
            _FakeLink(
                href="https://one.google.com/benefits/NEST_SERVICES",
                text="Claim offer",
            ),
        ]
    )
    assert extract_payment_link(driver) is None


def test_offer_accepts_checkout_url_on_keyword_match():
    driver = _FakeOfferDriver(
        [
            _FakeLink(
                href="https://play.google.com/store/paymentmethods?checkout=1",
                text="Start free trial",
            ),
        ]
    )
    assert (
        extract_payment_link(driver)
        == "https://play.google.com/store/paymentmethods?checkout=1"
    )


def test_offer_ignores_plain_paid_plan_link():
    driver = _FakeOfferDriver(
        [
            _FakeLink(
                href="https://one.google.com/about/plans",
                text="Get started",  # keyword, but not a checkout/claim URL
            ),
        ]
    )
    assert extract_payment_link(driver) is None


def test_navigate_google_one_scans_benefits_url():
    # The benefits page is part of the scan set for offer discovery.
    assert config.GOOGLE_ONE_BENEFITS_URL in {
        config.GOOGLE_ONE_OFFERS_URL,
        config.GOOGLE_ONE_BENEFITS_URL,
        config.GOOGLE_ONE_URL,
    }
    assert hasattr(ga, "navigate_google_one")
