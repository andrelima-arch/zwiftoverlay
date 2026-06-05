from app.core.events import EventLoop
from app.sensors.reader import SensorReader


class FakeEventLoop:
    def __init__(self):
        self.callbacks = []
        self.cancelled = []

    def call_later(self, _ms, callback, *args):
        timer_id = f"timer-{len(self.callbacks)}"
        self.callbacks.append((timer_id, callback, args))
        return timer_id

    def cancel(self, timer_id):
        self.cancelled.append(timer_id)

    def call_soon_threadsafe(self, callback, *args, **kwargs):
        callback(*args, **kwargs)

    def run_timer(self, timer_id):
        for current_timer_id, callback, args in list(self.callbacks):
            if current_timer_id == timer_id:
                callback(*args)
                return


def test_reader_marks_device_connected_only_after_connected_status():
    reader = SensorReader()
    try:
        connected = []
        disconnected = []
        reader.device_connected.connect(lambda address, label: connected.append((address, label)))
        reader.device_disconnected.connect(lambda address: disconnected.append(address))

        reader.connect_device("AA:BB", "ftms", {"address": "AA:BB", "service_type": "ftms"})

        assert reader._connecting_devices == {"AA:BB"}
        assert reader._connected_devices == {}

        reader._on_connection_status("AA:BB", "Connected")

        assert reader._connecting_devices == set()
        assert reader._connected_devices == {"AA:BB": "ftms"}
        assert connected == [("AA:BB", "Rolo inteligente (FTMS)")]

        reader._on_connection_status("AA:BB", "Disconnected")

        assert reader._connected_devices == {}
        assert disconnected == ["AA:BB"]
    finally:
        reader.stop()


def test_reader_keeps_zero_values_while_source_connected_and_clears_on_disconnect():
    reader = SensorReader()
    try:
        updates = []
        reader.sensor_data_updated.connect(lambda data: updates.append(data))
        reader._on_connection_status("TRAINER", "Connected")

        reader._on_sensor_data("TRAINER", {"power": 0, "cadence": 0})

        assert updates[-1].power == 0
        assert updates[-1].cadence == 0

        reader._on_connection_status("TRAINER", "Disconnected")

        assert updates[-1].power is None
        assert updates[-1].cadence is None
    finally:
        reader.stop()


def test_reader_disconnects_trainer_metrics_without_clearing_hr_source():
    reader = SensorReader()
    try:
        updates = []
        reader.sensor_data_updated.connect(lambda data: updates.append(data))

        reader._on_connection_status("TRAINER", "Connected")
        reader._on_connection_status("GARMIN", "Connected")
        reader._on_sensor_data("TRAINER", {"power": 180, "cadence": 82})
        reader._on_sensor_data("GARMIN", {"heart_rate": 145})

        reader._on_connection_status("TRAINER", "Disconnected")

        assert updates[-1].power is None
        assert updates[-1].cadence is None
        assert updates[-1].heart_rate == 145
    finally:
        reader.stop()


def test_reader_serializes_ble_connections():
    reader = SensorReader()
    requested = []
    statuses = []
    reader._worker.request_connect = lambda address, service, details=None: requested.append(address) or True
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    try:
        reader.connect_device("TRAINER", "ftms", {"address": "TRAINER", "service_type": "ftms"})
        reader.connect_device("GARMIN", "hr", {"address": "GARMIN", "service_type": "hr"})

        assert requested == ["TRAINER"]
        assert reader._active_connect_address == "TRAINER"
        assert ("TRAINER", "Queued...") in statuses
        assert ("TRAINER", "Connecting...") in statuses

        reader._on_connection_status("TRAINER", "Connected")
        reader._drain_connect_queue()

        assert requested == ["TRAINER", "GARMIN"]
        assert reader._active_connect_address == "GARMIN"
    finally:
        reader.stop()


def test_reader_moves_kickr_from_queued_to_connecting():
    reader = SensorReader()
    requested = []
    statuses = []
    reader._worker.request_connect = lambda address, service, details=None: requested.append((address, service)) or True
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    try:
        reader.connect_device(
            "KICKR",
            "ftms",
            {"address": "KICKR", "name": "Wahoo KICKR", "service_type": "ftms"},
        )

        assert requested == [("KICKR", "ftms")]
        assert ("KICKR", "Queued...") in statuses
        assert ("KICKR", "Connecting...") in statuses
        assert reader._active_connect_address == "KICKR"
        assert "KICKR" not in reader._queued_addresses
    finally:
        reader.stop()


def test_reader_clears_stale_active_connection_and_drains_next_device():
    reader = SensorReader()
    requested = []
    reader._worker.request_connect = lambda address, service, details=None: requested.append(address) or True
    try:
        reader._active_connect_address = "HRM"
        reader._connecting_devices = {"KICKR"}
        reader._connect_queue.append(("KICKR", "ftms", {"address": "KICKR", "service_type": "ftms"}))
        reader._queued_addresses.add("KICKR")

        reader._drain_connect_queue()

        assert requested == ["KICKR"]
        assert reader._active_connect_address == "KICKR"
        assert "KICKR" not in reader._queued_addresses
    finally:
        reader.stop()


def test_reader_reports_error_when_ble_worker_does_not_accept_connection():
    reader = SensorReader()
    statuses = []
    reader._worker.request_connect = lambda address, service, details=None: False
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    try:
        reader.connect_device("KICKR", "ftms", {"address": "KICKR", "service_type": "ftms"})

        assert ("KICKR", "Error: BLE worker unavailable") in statuses
        assert reader._active_connect_address is None
        assert "KICKR" not in reader._connecting_devices
        assert "KICKR" not in reader._queued_addresses
    finally:
        reader.stop()


def test_reader_defers_manual_scan_while_ble_connection_is_active():
    reader = SensorReader()
    requested_scans = []
    statuses = []
    reader._worker.request_scan = lambda: requested_scans.append(True)
    reader._worker.request_connect = lambda address, service, details=None: True
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    try:
        reader.connect_device("TRAINER", "ftms", {"address": "TRAINER", "service_type": "ftms"})
        reader.scan()

        assert requested_scans == []
        assert reader._pending_scan is True
        assert ("scanner", "Scan queued until BLE is idle") in statuses
    finally:
        reader.stop()


def test_reader_exposes_qz_dircon_discovery_and_routes_connection():
    reader = SensorReader()
    found = []
    connected_details = []

    class Device:
        address = "qz-dircon:192.168.1.42:41000:QZ123"
        name = "QZ Wahoo"
        service_type = "qz_dircon"
        compatibility_hint = "QZ Wi-Fi / Wahoo DIRCON"
        compatibility_profile = "qz_dircon"
        host = "192.168.1.42"
        port = 41000
        serial_number = "QZ123"
        mac_address = "AA:BB"
        source_type = "qz_dircon"

    reader.network_device_found.connect(lambda device: found.append(device))
    reader._qz_wifi_worker.connect_dircon = lambda details: connected_details.append(details)
    try:
        reader._on_network_device_found(Device())
        reader.connect_network_device(
            Device.address,
            "qz_dircon",
            {"address": Device.address, "host": Device.host, "port": str(Device.port)},
        )

        assert found[0].address == Device.address
        assert connected_details == [{"address": Device.address, "host": Device.host, "port": "41000"}]
    finally:
        reader.stop()


def test_reader_switches_active_qz_dircon_connection_to_new_network_device():
    reader = SensorReader()
    stopped = []
    connected_details = []
    statuses = []
    disconnected = []
    old_address = "qz-dircon:192.168.1.42:41000:HRM"
    new_address = "qz-dircon:192.168.1.43:41000:KICKR"
    reader._qz_wifi_worker.stop = lambda: stopped.append(True)
    reader._qz_wifi_worker.connect_dircon = lambda details: connected_details.append(details)
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    reader.device_disconnected.connect(lambda address: disconnected.append(address))
    try:
        reader._connected_devices[old_address] = "qz_dircon"

        reader.connect_network_device(
            new_address,
            "qz_dircon",
            {"address": new_address, "host": "192.168.1.43", "port": "41000"},
        )

        assert stopped == [True]
        assert old_address in disconnected
        assert (old_address, "Disconnected") in statuses
        assert (new_address, "Queued...") in statuses
        assert connected_details == [{"address": new_address, "host": "192.168.1.43", "port": "41000"}]
        assert new_address in reader._network_connecting_devices
    finally:
        reader.stop()


def test_reader_exposes_qz_android_websocket_and_routes_connection():
    reader = SensorReader()
    found = []
    connected_details = []

    class Device:
        address = "qz-ws:192.168.1.50:34107"
        name = "QZ Android 192.168.1.50"
        service_type = "qz_websocket"
        compatibility_hint = "QZ Wi-Fi / Android app"
        compatibility_profile = "qz_websocket"
        host = "192.168.1.50"
        port = 34107
        serial_number = ""
        mac_address = ""
        source_type = "qz_websocket"

    reader.network_device_found.connect(lambda device: found.append(device))
    reader._qz_wifi_worker.connect_qz_websocket = lambda details: connected_details.append(details)
    try:
        reader._on_network_device_found(Device())
        reader.connect_network_device(
            Device.address,
            "qz_websocket",
            {"address": Device.address, "host": Device.host, "port": str(Device.port)},
        )

        assert found[0].address == Device.address
        assert connected_details == [{"address": Device.address, "host": Device.host, "port": "34107"}]
    finally:
        reader.stop()


def test_reader_switches_active_qz_connection_to_qz_android_websocket():
    reader = SensorReader()
    stopped = []
    connected_details = []
    old_address = "qz-dircon:192.168.1.42:41000:HRM"
    new_address = "qz-ws:192.168.1.50:34107"
    reader._qz_wifi_worker.stop = lambda: stopped.append(True)
    reader._qz_wifi_worker.connect_qz_websocket = lambda details: connected_details.append(details)
    try:
        reader._connected_devices[old_address] = "qz_dircon"

        reader.connect_network_device(
            new_address,
            "qz_websocket",
            {"address": new_address, "host": "192.168.1.50", "port": "34107"},
        )

        assert stopped == [True]
        assert old_address not in reader._connected_devices
        assert connected_details == [{"address": new_address, "host": "192.168.1.50", "port": "34107"}]
        assert new_address in reader._network_connecting_devices
    finally:
        reader.stop()


def test_reader_qz_dircon_disconnection_clears_only_qz_source():
    reader = SensorReader()
    try:
        updates = []
        reader.sensor_data_updated.connect(lambda data: updates.append(data))
        source_id = "qz-dircon:192.168.1.42:41000:QZ123"

        reader._on_sensor_data(source_id, {"power": 190, "cadence": 80})
        reader._on_sensor_data("GARMIN", {"heart_rate": 142})
        reader._on_qz_connection_status(source_id, "Disconnected")

        assert updates[-1].power is None
        assert updates[-1].cadence is None
        assert updates[-1].heart_rate == 142
    finally:
        reader.stop()


def test_reader_qz_network_timeout_clears_queued_connection(monkeypatch):
    fake_loop = FakeEventLoop()
    monkeypatch.setattr(EventLoop, "get", classmethod(lambda cls: fake_loop))
    reader = SensorReader()
    statuses = []
    stopped = []
    source_id = "qz-dircon:192.168.1.42:41000:QZ123"
    reader._qz_wifi_worker.connect_dircon = lambda _details: None
    reader._qz_wifi_worker.stop = lambda: stopped.append(True)
    reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
    try:
        reader.connect_network_device(
            source_id,
            "qz_dircon",
            {"address": source_id, "host": "192.168.1.42", "port": "41000"},
        )
        fake_loop.run_timer(reader._network_connect_attempt_timers[source_id])

        assert (source_id, "Error: QZ Wi-Fi connection timed out") in statuses
        assert source_id not in reader._network_connecting_devices
        assert source_id not in reader._connected_devices
        assert stopped == [True]
    finally:
        reader.stop()


def test_reader_ble_timeout_does_not_block_qz_network_connection(monkeypatch):
    fake_loop = FakeEventLoop()
    monkeypatch.setattr(EventLoop, "get", classmethod(lambda cls: fake_loop))
    reader = SensorReader()
    connected_details = []
    reader._worker.request_connect = lambda _address, _service, _details=None: True
    reader._worker.request_disconnect = lambda _address: None
    reader._qz_wifi_worker.connect_dircon = lambda details: connected_details.append(details)
    try:
        reader.connect_device("S20And", "ftms", {"address": "S20And", "service_type": "ftms"})
        fake_loop.run_timer(reader._connect_attempt_timer)

        reader.connect_network_device(
            "qz-dircon:192.168.1.43:41000:KICKR",
            "qz_dircon",
            {"address": "qz-dircon:192.168.1.43:41000:KICKR", "host": "192.168.1.43", "port": "41000"},
        )

        assert connected_details == [
            {"address": "qz-dircon:192.168.1.43:41000:KICKR", "host": "192.168.1.43", "port": "41000"}
        ]
    finally:
        reader.stop()


def test_reader_normalizes_qz_dircon_connected_status():
    reader = SensorReader()
    try:
        statuses = []
        connected = []
        source_id = "qz-dircon:192.168.1.42:41000:QZ123"
        reader._qz_wifi_worker.connect_dircon = lambda _details: None
        reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
        reader.device_connected.connect(lambda address, label: connected.append((address, label)))

        reader.connect_network_device(
            source_id,
            "qz_dircon",
            {"address": source_id, "host": "192.168.1.42", "port": "41000"},
        )
        reader._on_qz_connection_status(source_id, "Connected QZ DIRCON QZ Wahoo")

        assert (source_id, "Connected") in statuses
        assert reader._network_connecting_devices == set()
        assert reader._connected_devices[source_id] == "qz_dircon"
        assert connected == [(source_id, "QZ Wi-Fi / Wahoo DIRCON")]
    finally:
        reader.stop()


def test_reader_normalizes_qz_android_websocket_connected_status():
    reader = SensorReader()
    try:
        statuses = []
        connected = []
        source_id = "qz-ws:192.168.1.50:34107"
        reader._qz_wifi_worker.connect_qz_websocket = lambda _details: None
        reader.connection_status_changed.connect(lambda address, status: statuses.append((address, status)))
        reader.device_connected.connect(lambda address, label: connected.append((address, label)))

        reader.connect_network_device(
            source_id,
            "qz_websocket",
            {"address": source_id, "host": "192.168.1.50", "port": "34107"},
        )
        reader._on_qz_connection_status(source_id, "Connected QZ WebSocket 192.168.1.50")

        assert (source_id, "Connected") in statuses
        assert reader._network_connecting_devices == set()
        assert reader._connected_devices[source_id] == "qz_websocket"
        assert connected == [(source_id, "QZ Wi-Fi / Android app")]
    finally:
        reader.stop()
