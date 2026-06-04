from app.sensors.qz_mqtt import DEFAULT_QZ_MQTT_PORT, parse_qz_mqtt_message


def test_qz_mqtt_maps_watts_cadence_and_heart_rate_topics():
    assert parse_qz_mqtt_message("QZ/bike/watts/current", b"201.6") == {"power": 202}
    assert parse_qz_mqtt_message("QZ/bike/bike/cadence/current", "88") == {"cadence": 88}
    assert parse_qz_mqtt_message("QZ/bike/heart/current", "145") == {"heart_rate": 145}


def test_qz_mqtt_maps_workout_topics_from_qz():
    assert parse_qz_mqtt_message("QZ/bike/workout/watts/current", b"201.6") == {"power": 202}
    assert parse_qz_mqtt_message("QZ/bike/workout/bike/cadence/current", "88") == {"cadence": 88}
    assert parse_qz_mqtt_message("QZ/bike/workout/heart/current", "145") == {"heart_rate": 145}


def test_qz_mqtt_keeps_zero_values():
    assert parse_qz_mqtt_message("QZ/bike/watts/current", "0") == {"power": 0}
    assert parse_qz_mqtt_message("QZ/bike/bike/cadence/current", "0") == {"cadence": 0}
    assert parse_qz_mqtt_message("QZ/bike/heart/current", "0") == {"heart_rate": 0}


def test_qz_mqtt_device_connected_false_clears_source():
    assert parse_qz_mqtt_message("QZ/bike/workout/device/connected", "false") == {
        "power": None,
        "cadence": None,
        "heart_rate": None,
    }
    assert parse_qz_mqtt_message("QZ/bike/device/connected", "0") == {
        "power": None,
        "cadence": None,
        "heart_rate": None,
    }


def test_qz_mqtt_status_offline_clears_source():
    assert parse_qz_mqtt_message("QZ/bike/status", "offline") == {
        "power": None,
        "cadence": None,
        "heart_rate": None,
    }
    assert parse_qz_mqtt_message("QZ/bike/status", "online") == {}


def test_qz_mqtt_default_port():
    assert DEFAULT_QZ_MQTT_PORT == 1883
