from app.sensors.qz_dircon import DirconDevice
from app.sensors.qz_wifi import NetworkSensorDevice
from app.sensors.qz_wifi import QzWifiWorker
from app.sensors.qz_wifi import parse_proform_control_event, parse_proform_telnet_metrics


def test_proform_control_event_maps_watts_cadence_and_heart_rate():
    payload = {
        "values": {
            "RPM": 88.6,
            "Current Watts": 210.4,
            "Heart Rate": 145,
        }
    }

    assert parse_proform_control_event(payload) == {
        "power": 210,
        "cadence": 89,
        "heart_rate": 145,
    }


def test_proform_control_event_accepts_italian_watts_key_and_zero_values():
    payload = {"values": {"RPM": 0, "Watt attuali": 0}}

    assert parse_proform_control_event(payload) == {
        "power": 0,
        "cadence": 0,
    }


def test_proform_telnet_metrics_parse_qz_variable_names():
    text = "Current Watts: 198\nCur RPM: 82\nHR: 144\n"

    assert parse_proform_telnet_metrics(text) == {
        "power": 198,
        "cadence": 82,
        "heart_rate": 144,
    }


def test_network_sensor_device_represents_qz_dircon_as_connectable_source():
    device = NetworkSensorDevice.from_dircon(
        DirconDevice(
            name="QZ Wahoo",
            host="192.168.1.42",
            port=41000,
            serial_number="QZ123",
            mac_address="AA:BB",
            service_uuids=["00001826-0000-1000-8000-00805f9b34fb"],
        )
    )

    assert device.address == "qz-dircon:192.168.1.42:41000:QZ123"
    assert device.service_type == "qz_dircon"
    assert device.host == "192.168.1.42"
    assert device.port == 41000
    assert device.compatibility_hint == "QZ Wi-Fi / Wahoo DIRCON"


def test_qz_wifi_discovery_reports_missing_zeroconf(monkeypatch):
    monkeypatch.setattr("app.sensors.qz_wifi.is_zeroconf_available", lambda: False)
    worker = QzWifiWorker()
    statuses = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))

    worker._run_discovery()

    assert statuses[-1] == ("qz_wifi", "QZ Wi-Fi indisponível: zeroconf não instalado")


def test_qz_wifi_discovery_reports_mdns_scanner_error(monkeypatch):
    monkeypatch.setattr("app.sensors.qz_wifi.is_zeroconf_available", lambda: True)

    class FailingScanner:
        def discover(self):
            raise RuntimeError("bad service type")

    monkeypatch.setattr("app.sensors.qz_wifi.DirconMdnsScanner", FailingScanner)
    worker = QzWifiWorker()
    statuses = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))

    worker._run_discovery()

    assert statuses[-1] == (
        "qz_wifi",
        "QZ Wi-Fi erro na descoberta mDNS: bad service type",
    )


def test_qz_wifi_queues_dircon_connection_while_discovery_is_busy():
    worker = QzWifiWorker()
    statuses = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))

    class BusyThread:
        def is_alive(self):
            return True

    device = DirconDevice(
        name="QZ Wahoo",
        host="192.168.1.42",
        port=36866,
        serial_number="QZ123",
    )
    worker._thread = BusyThread()

    worker.connect_dircon(device)

    assert worker._pending_dircon_device == device
    assert (device.source_id, "Queued...") in statuses
    assert ("qz_wifi", "QZ Wi-Fi ocupado; conexão enfileirada") in statuses
