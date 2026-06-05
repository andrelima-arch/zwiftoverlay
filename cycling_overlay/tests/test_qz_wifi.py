import threading

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


def test_network_sensor_device_represents_qz_android_websocket_as_connectable_source():
    device = NetworkSensorDevice.from_qz_websocket("192.168.1.50")

    assert device.address == "qz-ws:192.168.1.50:34107"
    assert device.service_type == "qz_websocket"
    assert device.host == "192.168.1.50"
    assert device.port == 34107
    assert device.compatibility_hint == "QZ Wi-Fi / Android app"


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


def test_qz_wifi_auto_scan_busy_emits_terminal_status():
    worker = QzWifiWorker()
    statuses = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))

    class BusyThread:
        def is_alive(self):
            return True

    worker._thread = BusyThread()

    worker.start_auto_scan()

    assert statuses[-1] == ("qz_wifi", "QZ Wi-Fi ocupado; scan em andamento")


def test_qz_wifi_queues_websocket_connection_while_worker_is_busy():
    worker = QzWifiWorker()
    statuses = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))

    class BusyThread:
        def is_alive(self):
            return True

    worker._thread = BusyThread()

    worker.connect_qz_websocket({"host": "192.168.1.50", "port": "34107"})

    assert worker._pending_qz_websocket == ("192.168.1.50", 34107)
    assert ("qz-ws:192.168.1.50:34107", "Queued...") in statuses
    assert ("qz_wifi", "QZ Wi-Fi ocupado; conexão enfileirada") in statuses


def test_qz_pending_websocket_connection_starts_after_worker_finishes(monkeypatch):
    worker = QzWifiWorker()
    worker._thread = threading.current_thread()
    worker._pending_qz_websocket = ("192.168.1.50", 34107)
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr("app.sensors.qz_wifi.threading.Thread", FakeThread)

    worker._start_pending_dircon_if_needed()

    target, args, daemon = started[0]
    assert target.__func__ is QzWifiWorker._run_qz_websocket_client
    assert args == ("192.168.1.50", 34107)
    assert daemon is True
    assert worker._pending_qz_websocket is None


def test_qz_pending_websocket_connection_starts_after_dircon_client_finishes(monkeypatch):
    worker = QzWifiWorker()
    worker._thread = threading.current_thread()
    worker._pending_qz_websocket = ("192.168.1.50", 34107)
    worker._try_qz_dircon = lambda _device: False
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr("app.sensors.qz_wifi.threading.Thread", FakeThread)

    worker._run_dircon_client(
        DirconDevice(
            name="QZ Wahoo",
            host="192.168.1.42",
            port=36866,
            serial_number="QZ123",
        )
    )

    target, args, daemon = started[0]
    assert target.__func__ is QzWifiWorker._run_qz_websocket_client
    assert args == ("192.168.1.50", 34107)
    assert daemon is True
    assert worker._pending_qz_websocket is None


def test_qz_pending_dircon_connection_starts_after_websocket_client_finishes(monkeypatch):
    worker = QzWifiWorker()
    worker._thread = threading.current_thread()
    pending_device = DirconDevice(
        name="QZ Wahoo",
        host="192.168.1.42",
        port=36866,
        serial_number="QZ123",
    )
    worker._pending_dircon_device = pending_device
    worker._try_qz_websocket = lambda _host, _port: False
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr("app.sensors.qz_wifi.threading.Thread", FakeThread)

    worker._run_qz_websocket_client("192.168.1.50", 34107)

    target, args, daemon = started[0]
    assert target.__func__ is QzWifiWorker._run_dircon_client
    assert args == (pending_device,)
    assert daemon is True
    assert worker._pending_dircon_device is None


def test_qz_auto_scan_falls_back_to_qz_android_websocket(monkeypatch):
    monkeypatch.setattr("app.sensors.qz_wifi.is_zeroconf_available", lambda: True)

    class EmptyMdnsScanner:
        def discover(self):
            return []

    class FakeNetworkScanner:
        def reachable_hosts(self, ports=(80, 23)):
            if ports == (34107,):
                return ["192.168.1.50"]
            return []

        def reachable_endpoints(self, _ports):
            return []

    monkeypatch.setattr("app.sensors.qz_wifi.DirconMdnsScanner", EmptyMdnsScanner)
    monkeypatch.setattr("app.sensors.qz_wifi.NetworkDeviceScanner", FakeNetworkScanner)
    worker = QzWifiWorker()
    statuses = []
    devices = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))
    worker.device_found.emit_safe = lambda device: devices.append(device)

    worker._run_auto_scan()

    assert devices[0].address == "qz-ws:192.168.1.50:34107"
    assert devices[0].service_type == "qz_websocket"
    assert statuses[-1] == ("qz_wifi", "QZ Wi-Fi encontrado: 1 fonte(s) disponível(is)")


def test_qz_auto_scan_still_finds_qz_android_when_dircon_is_found(monkeypatch):
    monkeypatch.setattr("app.sensors.qz_wifi.is_zeroconf_available", lambda: True)

    dircon_device = DirconDevice(
        name="QZ Wahoo",
        host="192.168.1.42",
        port=36866,
        serial_number="QZ123",
    )

    class FoundMdnsScanner:
        def discover(self):
            return [dircon_device]

    class FakeNetworkScanner:
        def reachable_hosts(self, ports=(80, 23)):
            if ports == (34107,):
                return ["192.168.1.50"]
            return []

        def reachable_endpoints(self, _ports):
            return []

    monkeypatch.setattr("app.sensors.qz_wifi.DirconMdnsScanner", FoundMdnsScanner)
    monkeypatch.setattr("app.sensors.qz_wifi.NetworkDeviceScanner", FakeNetworkScanner)
    worker = QzWifiWorker()
    devices = []
    worker.device_found.emit_safe = lambda device: devices.append(device)

    worker._run_auto_scan()

    assert [device.service_type for device in devices] == ["qz_dircon", "qz_websocket"]
    assert devices[1].address == "qz-ws:192.168.1.50:34107"


def test_qz_auto_scan_falls_back_to_qz_dircon_default_ports_when_mdns_misses(monkeypatch):
    monkeypatch.setattr("app.sensors.qz_wifi.is_zeroconf_available", lambda: True)

    class EmptyMdnsScanner:
        def discover(self):
            return []

    class FakeNetworkScanner:
        def reachable_hosts(self, ports=(80, 23)):
            return []

        def reachable_endpoints(self, ports):
            assert ports == (36866, 36867, 36868, 36869)
            return [("192.168.1.50", 36866), ("192.168.1.50", 36867)]

    monkeypatch.setattr("app.sensors.qz_wifi.DirconMdnsScanner", EmptyMdnsScanner)
    monkeypatch.setattr("app.sensors.qz_wifi.NetworkDeviceScanner", FakeNetworkScanner)
    worker = QzWifiWorker()
    statuses = []
    devices = []
    worker.connection_status.emit_safe = lambda address, status: statuses.append((address, status))
    worker.device_found.emit_safe = lambda device: devices.append(device)

    worker._run_auto_scan()

    assert [device.service_type for device in devices] == ["qz_dircon", "qz_dircon"]
    assert devices[0].address.startswith("qz-dircon:192.168.1.50:36866:")
    assert devices[1].address.startswith("qz-dircon:192.168.1.50:36867:")
    assert devices[0].address != devices[1].address
    assert "KICKR" in devices[0].name
    assert "HRM" in devices[1].name
    assert statuses[-1] == ("qz_wifi", "QZ Wi-Fi encontrado: 2 fonte(s) disponível(is)")
