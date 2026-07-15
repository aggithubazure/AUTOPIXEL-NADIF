from __future__ import annotations

import re
from types import SimpleNamespace

from handlers import ui


def context_with_lang(lang=None):
    data = {}
    if lang is not None:
        data["lang"] = lang
    return SimpleNamespace(user_data=data)


def test_get_user_lang_defaults_to_english_for_missing_or_unknown():
    assert ui.get_user_lang(context_with_lang()) == "en"
    assert ui.get_user_lang(context_with_lang("fr")) == "en"


def test_set_user_lang_persists_supported_or_default_language():
    context = context_with_lang()
    assert ui.set_user_lang(context, "id") == "id"
    assert context.user_data["lang"] == "id"
    assert ui.set_user_lang(context, "fr") == "en"
    assert context.user_data["lang"] == "en"


def test_tr_returns_different_known_strings_for_en_and_id():
    en = context_with_lang("en")
    indonesian = context_with_lang("id")
    assert ui.tr(en, "lang_set") == "🌐 Language set to English."
    assert ui.tr(indonesian, "lang_set") == "🌐 Bahasa diubah ke Indonesia."
    assert ui.tr(en, "lang_set") != ui.tr(indonesian, "lang_set")


def test_tr_formats_template_values():
    context = context_with_lang("en")
    assert "3m 4s" in ui.tr(context, "offer_cooldown_wait", mins=3, secs=4)


def test_tr_unknown_key_returns_key():
    assert ui.tr(context_with_lang("en"), "missing_key") == "missing_key"


def test_login_security_notice_present_in_both_languages():
    en = ui.tr(context_with_lang("en"), "login_security_notice")
    indonesian = ui.tr(context_with_lang("id"), "login_security_notice")
    assert en != "login_security_notice"
    assert indonesian != "login_security_notice"
    assert "/cancel" in en
    assert "/cancel" in indonesian
    assert en != indonesian


def test_menu_label_returns_translated_labels():
    assert ui.menu_label("menu_check_offer", lang="en")
    assert ui.menu_label("menu_check_offer", lang="id")
    assert ui.menu_label("menu_check_offer", lang="en") != ui.menu_label("menu_check_offer", lang="id")


def test_button_regex_matches_menu_label_in_supported_languages():
    pattern = re.compile(ui.button_regex("menu_login"))
    assert pattern.match(ui.menu_label("menu_login", lang="en"))
    assert pattern.match(ui.menu_label("menu_login", lang="id"))
    assert not pattern.match("not a menu label")


def test_button_regex_unknown_key_characterization():
    # characterization: locks current behavior for unknown keys: an empty alternative matches only empty string.
    assert ui.button_regex("missing_key") == "^()$"


def test_section_header_escapes_translated_text():
    context = context_with_lang("en")
    header = ui.section_header(context, "section_quick_start")
    assert header == "[·] <b>Quick Start</b>"


def test_menu_callback_data_current_values():
    assert ui.menu_callback_data("menu_login") == "menu:login"
    assert ui.menu_callback_data("menu_home") == "menu:home"
