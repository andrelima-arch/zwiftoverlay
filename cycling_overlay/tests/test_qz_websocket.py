from app.sensors.qz_websocket import DEFAULT_QZ_WS_PORT, parse_qz_workout_event


def test_qz_workout_event_maps_power_cadence_and_heart_rate():
    payload = '{"watts": 210.4, "cadence": 88.6, "heart": 145}'

    assert parse_qz_workout_event(payload) == {
        "power": 210,
        "cadence": 89,
        "heart_rate": 145,
    }


def test_qz_workout_event_keeps_zero_values():
    assert parse_qz_workout_event({"watts": 0, "cadence": 0, "heart": 0}) == {
        "power": 0,
        "cadence": 0,
        "heart_rate": 0,
    }


def test_qz_workout_event_ignores_missing_fields():
    assert parse_qz_workout_event({"watts": 180}) == {"power": 180}


def test_qz_workout_event_device_disconnected_clears_source():
    assert parse_qz_workout_event({"deviceConnected": False, "watts": 0, "cadence": 0, "heart": 0}) == {
        "power": None,
        "cadence": None,
        "heart_rate": None,
    }


def test_qz_workout_event_accepts_common_cadence_and_heart_keys():
    assert parse_qz_workout_event({"power": 199.8, "bikeCadence": 91.2, "heartRate": 143}) == {
        "power": 200,
        "cadence": 91,
        "heart_rate": 143,
    }


def test_qz_default_port_matches_qz_docs():
    assert DEFAULT_QZ_WS_PORT == 34107
