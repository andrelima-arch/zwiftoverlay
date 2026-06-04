from app.core.config_manager import ConfigManager


def test_config_persists_profile_intervals_zwo_and_sensors(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.weight_kg = 82.5
    config.ftp = 290
    config.profile_source = "intervals_icu"
    config.intervals_api_key = "secret"
    config.intervals_athlete_id = "athlete-1"
    config.last_zwo_folder = "/tmp/workouts"
    config.sensor_addresses = {
        "hr": "AA:BB",
        "ftms": "CC:DD",
    }

    loaded = ConfigManager()
    assert loaded.weight_kg == 82.5
    assert loaded.ftp == 290
    assert loaded.profile_source == "intervals_icu"
    assert loaded.intervals_api_key == "secret"
    assert loaded.intervals_athlete_id == "athlete-1"
    assert loaded.last_zwo_folder == "/tmp/workouts"
    assert loaded.sensor_addresses == {"hr": "AA:BB", "ftms": "CC:DD"}


def test_config_persists_separate_manual_and_intervals_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.manual_weight_kg = 92.0
    config.manual_ftp = 310
    config.intervals_weight_kg = 85.7
    config.intervals_ftp = 250
    config.profile_source = "intervals_icu"
    config.weight_kg = 85.7
    config.ftp = 250

    loaded = ConfigManager()
    assert loaded.manual_weight_kg == 92.0
    assert loaded.manual_ftp == 310
    assert loaded.intervals_weight_kg == 85.7
    assert loaded.intervals_ftp == 250
    assert loaded.weight_kg == 85.7
    assert loaded.ftp == 250


def test_config_migrates_legacy_active_profile_to_manual(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.weight_kg = 80.0
    config.ftp = 280

    loaded = ConfigManager()
    assert loaded.manual_weight_kg == 80.0
    assert loaded.manual_ftp == 280


def test_config_invalid_profile_source_defaults_to_manual(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.profile_source = "invalid"

    assert ConfigManager().profile_source == "manual"


def test_config_persists_ui_language(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    assert config.ui_language == "en"

    config.ui_language = "pt"
    assert ConfigManager().ui_language == "pt"

    config.ui_language = "invalid"
    assert ConfigManager().ui_language == "en"


def test_config_persists_sensor_details(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.sensor_addresses = {
        "ftms": {
            "address": "CC:DD",
            "name": "KICKR CORE",
            "service_type": "ftms",
            "compatibility_hint": "FTMS / QZ match",
        }
    }

    assert ConfigManager().sensor_addresses == {
        "ftms": {
            "address": "CC:DD",
            "name": "KICKR CORE",
            "service_type": "ftms",
            "compatibility_hint": "FTMS / QZ match",
        }
    }


def test_config_persists_known_ble_devices(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.known_ble_devices = {
        "CC:DD": {
            "address": "CC:DD",
            "name": "THINK X2MAX",
            "service_type": "ftms",
            "compatibility_hint": "FTMS / ThinkRider QZ match",
            "compatibility_profile": "think_x",
            "last_seen": "2026-06-03T00:00:00+00:00",
        }
    }

    assert ConfigManager().known_ble_devices == {
        "CC:DD": {
            "address": "CC:DD",
            "name": "THINK X2MAX",
            "service_type": "ftms",
            "compatibility_hint": "FTMS / ThinkRider QZ match",
            "compatibility_profile": "think_x",
            "last_seen": "2026-06-03T00:00:00+00:00",
        }
    }


def test_config_persists_qz_websocket_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.qz_ws_enabled = True
    config.qz_ws_host = "192.168.1.42"
    config.qz_ws_port = 34107
    config.qz_ws_auto_reconnect = False

    loaded = ConfigManager()
    assert loaded.qz_ws_enabled is True
    assert loaded.qz_ws_host == "192.168.1.42"
    assert loaded.qz_ws_port == 34107
    assert loaded.qz_ws_auto_reconnect is False


def test_config_persists_qz_wifi_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.qz_wifi_enabled = True

    assert ConfigManager().qz_wifi_enabled is True


def test_config_persists_qz_dircon_manual_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.qz_dircon_host = "192.168.1.42"
    config.qz_dircon_port = 41000

    loaded = ConfigManager()
    assert loaded.qz_dircon_host == "192.168.1.42"
    assert loaded.qz_dircon_port == 41000


def test_config_persists_qz_mqtt_settings(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config_manager.user_config_dir", lambda _: str(tmp_path))

    config = ConfigManager()
    config.qz_mqtt_enabled = True
    config.qz_mqtt_host = "192.168.1.50"
    config.qz_mqtt_port = 1884
    config.qz_mqtt_device = "trainer"
    config.qz_mqtt_username = "user"
    config.qz_mqtt_password = "secret"

    loaded = ConfigManager()
    assert loaded.qz_mqtt_enabled is True
    assert loaded.qz_mqtt_host == "192.168.1.50"
    assert loaded.qz_mqtt_port == 1884
    assert loaded.qz_mqtt_device == "trainer"
    assert loaded.qz_mqtt_username == "user"
    assert loaded.qz_mqtt_password == "secret"
