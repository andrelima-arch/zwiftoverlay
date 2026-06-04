from app.sensors.reader import SensorReader


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
    reader._worker.request_connect = lambda address, service, details=None: requested.append(address)
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


def test_reader_defers_manual_scan_while_ble_connection_is_active():
    reader = SensorReader()
    requested_scans = []
    statuses = []
    reader._worker.request_scan = lambda: requested_scans.append(True)
    reader._worker.request_connect = lambda address, service, details=None: None
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
