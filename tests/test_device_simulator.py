from __future__ import annotations

import config
from services import device_simulator


def test_create_device_profile_uses_requested_profile_values():
    profile_name = "pixel_9_pro_xl"
    preset = config.DEVICE_PRESETS[profile_name]
    profile = device_simulator.create_device_profile(profile_name=profile_name)

    assert profile.profile_name == profile_name
    assert profile.model == preset["model"]
    assert profile.android_version == preset["android_version"]
    assert f"Android {preset['android_version']}" in profile.user_agent
    assert preset["model"] in profile.user_agent
    assert profile.build_id in device_simulator.DEVICE_BUILDS_BY_PROFILE[profile_name]


def test_client_hints_headers_include_platform_version_and_model():
    profile = device_simulator.create_device_profile(profile_name="pixel_10_pro")
    headers = profile.client_hints_headers()
    assert headers["Sec-CH-UA-Mobile"] == "?1"
    assert headers["Sec-CH-UA-Platform"] == '"Android"'
    assert headers["Sec-CH-UA-Platform-Version"] == f'"{profile.android_version}.0.0"'
    assert headers["Sec-CH-UA-Model"] == f'"{profile.model}"'
    assert headers["Sec-CH-UA-Full-Version"] == f'"{profile.chrome_version}"'


def test_as_headers_adds_accept_language_and_client_hints():
    profile = device_simulator.create_device_profile(profile_name="pixel_10_pro_fold")
    headers = profile.as_headers()
    assert headers["Accept-Language"] == profile.accept_language
    assert headers["Sec-CH-UA-Model"] == f'"{profile.model}"'


def test_user_agent_metadata_shape():
    profile = device_simulator.create_device_profile(profile_name="pixel_9_pro")
    metadata = profile.user_agent_metadata()
    assert metadata["mobile"] is True
    assert metadata["platform"] == "Android"
    assert metadata["platformVersion"] == f"{profile.android_version}.0.0"
    assert metadata["model"] == profile.model
    assert metadata["brands"] == profile.user_agent_brands()
    assert metadata["fullVersionList"] == profile.user_agent_full_version_list()


def test_navigator_overrides_js_is_non_empty_and_contains_spoof_tokens():
    profile = device_simulator.create_device_profile(profile_name="pixel_10_pro")
    script = profile.navigator_overrides_js()
    assert isinstance(script, str)
    assert "navigator" in script
    assert "userAgentData" in script
    assert "getHighEntropyValues" in script
    assert "webdriver" in script
    assert profile.model in script


def test_random_build_id_uses_profile_pool():
    for profile_name, build_pool in device_simulator.DEVICE_BUILDS_BY_PROFILE.items():
        assert device_simulator.random_build_id(profile_name) in build_pool


def test_get_specs_for_unknown_profile_falls_back_to_active_profile():
    assert device_simulator.get_specs_for_profile("unknown") is device_simulator.DEVICE_SPECS_BY_PROFILE[config.DEVICE_PROFILE_NAME]


def test_resolve_emulation_settings_prefers_network_identity():
    settings = device_simulator.resolve_emulation_settings({
        "timezone": "Asia/Jakarta",
        "latitude": "-6.2",
        "longitude": "106.8",
    })
    assert settings["timezone_id"] == "Asia/Jakarta"
    assert settings["geolocation_latitude"] == -6.2
    assert settings["geolocation_longitude"] == 106.8
    assert settings["geolocation_accuracy"] == config.EMULATION_GEO_ACCURACY
