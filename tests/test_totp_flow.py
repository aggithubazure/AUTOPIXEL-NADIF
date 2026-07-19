"""Tests for TOTP retry safety and the 2-Step Verification chooser handling."""

import time

import pyotp
from selenium.common.exceptions import NoSuchElementException

from handlers.offer_handlers import _generate_unused_totp_code
from services.google_automation import _select_authenticator_method

SECRET = "JBSWY3DPEHPK3PXP"


def test_generate_unused_totp_returns_current_when_no_last_code():
    assert _generate_unused_totp_code(SECRET, None) == pyotp.TOTP(SECRET).now()


def test_generate_unused_totp_returns_immediately_when_last_differs():
    assert _generate_unused_totp_code(SECRET, "000000") == pyotp.TOTP(SECRET).now()


def test_generate_unused_totp_is_time_bounded_when_window_has_not_rolled():
    now = pyotp.TOTP(SECRET).now()
    start = time.time()
    code = _generate_unused_totp_code(SECRET, now, timeout=0.2)
    elapsed = time.time() - start
    # Must never hang: bounded by the small timeout plus at most one 1s poll.
    assert elapsed < 3.0
    assert code.isdigit() and len(code) == 6


class _FakeElement:
    def __init__(self):
        self.clicked = False

    def click(self):
        self.clicked = True


class _FakeChooserDriver:
    """Minimal driver exposing find_element for the authenticator option."""

    def __init__(self, matching_xpath_substring):
        self._match = matching_xpath_substring
        self.clicked_element = None

    def find_element(self, by, value):
        if self._match in value:
            element = _FakeElement()
            self.clicked_element = element
            return element
        raise NoSuchElementException(value)


def test_select_authenticator_method_clicks_challenge_type_option():
    driver = _FakeChooserDriver('data-challengetype="6"')
    assert _select_authenticator_method(driver) is True
    assert driver.clicked_element is not None
    assert driver.clicked_element.clicked is True


def test_select_authenticator_method_clicks_text_option():
    driver = _FakeChooserDriver("Google Authenticator")
    assert _select_authenticator_method(driver) is True
    assert driver.clicked_element.clicked is True


def test_select_authenticator_method_returns_false_when_no_option():
    driver = _FakeChooserDriver("__never_matches__")
    assert _select_authenticator_method(driver) is False
