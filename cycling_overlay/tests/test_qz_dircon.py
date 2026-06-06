import sys
import threading
from types import ModuleType

from app.sensors.qz_dircon import (
    CSC_MEASUREMENT,
    DIRCON_DISCOVER_CHARACTERISTICS,
    DIRCON_DISCOVER_SERVICES,
    DIRCON_ENABLE_NOTIFICATIONS,
    DIRCON_HEADER_LENGTH,
    DIRCON_NOTIFICATION,
    FTMS_INDOOR_BIKE_DATA,
    FTMS_SERVICE,
    HR_MEASUREMENT,
    POWER_MEASUREMENT,
    POWER_SERVICE,
    DirconDevice,
    DirconPacket,
    DirconMdnsScanner,
    DirconTcpClient,
    dircon_browser_service_types,
    dircon_device_from_service_info,
    decode_dircon_frames,
    encode_dircon_request,
    normalize_dircon_service_type,
    parse_ble_service_uuids,
    parse_dircon_notification,
    uuid_bytes,
)


def _frame(identifier: int, sequence: int, payload: bytes) -> bytes:
    return bytes((1, identifier, sequence, 0, (len(payload) >> 8) & 0xFF, len(payload) & 0xFF)) + payload


def test_dircon_mdns_uuid_parser_accepts_short_and_full_uuids():
    assert parse_ble_service_uuids(
        "0x1826,00001818-0000-1000-8000-00805f9b34fb;1816"
    ) == [
        "00001826-0000-1000-8000-00805f9b34fb",
        "00001818-0000-1000-8000-00805f9b34fb",
        "00001816-0000-1000-8000-00805f9b34fb",
    ]


def test_dircon_service_type_normalizes_to_zeroconf_required_suffix():
    assert normalize_dircon_service_type("_wahoo-fitness-tnp._tcp.local") == (
        "_wahoo-fitness-tnp._tcp.local."
    )
    assert dircon_browser_service_types() == ("_wahoo-fitness-tnp._tcp.local.",)


def test_dircon_mdns_scanner_only_uses_canonical_zeroconf_service_type(monkeypatch):
    service_types = []

    class FakeServiceListener:
        pass

    class FakeZeroconf:
        def close(self):
            pass

    class FakeServiceBrowser:
        def __init__(self, _zeroconf, service_type, _listener):
            if not service_type.endswith(".local."):
                raise AssertionError(f"invalid service type: {service_type}")
            service_types.append(service_type)

        def cancel(self):
            pass

    monkeypatch.setattr("app.sensors.qz_dircon.is_zeroconf_available", lambda: True)
    zeroconf_module = ModuleType("zeroconf")
    zeroconf_module.ServiceBrowser = FakeServiceBrowser
    zeroconf_module.ServiceListener = FakeServiceListener
    zeroconf_module.Zeroconf = FakeZeroconf
    monkeypatch.setitem(sys.modules, "zeroconf", zeroconf_module)

    assert DirconMdnsScanner().discover(timeout=0) == []
    assert service_types == ["_wahoo-fitness-tnp._tcp.local."]


def test_dircon_mdns_scanner_returns_empty_list_when_browser_creation_fails(monkeypatch):
    class FakeServiceListener:
        pass

    class FakeZeroconf:
        def close(self):
            pass

    class FailingServiceBrowser:
        def __init__(self, *_args):
            raise RuntimeError("mDNS failed")

    monkeypatch.setattr("app.sensors.qz_dircon.is_zeroconf_available", lambda: True)
    zeroconf_module = ModuleType("zeroconf")
    zeroconf_module.ServiceBrowser = FailingServiceBrowser
    zeroconf_module.ServiceListener = FakeServiceListener
    zeroconf_module.Zeroconf = FakeZeroconf
    monkeypatch.setitem(sys.modules, "zeroconf", zeroconf_module)

    assert DirconMdnsScanner().discover(timeout=0) == []


class FakeServiceInfo:
    name = "QZ-Wahoo._wahoo-fitness-tnp._tcp.local."
    port = 41000
    addresses = [b"\xc0\xa8\x01\x2a"]
    properties = {
        b"mac-address": b"AA:BB:CC:DD:EE:FF",
        b"serial-number": b"QZ123",
        b"ble-service-uuids": b"0x1826,00001818-0000-1000-8000-00805f9b34fb",
    }


def test_dircon_mdns_service_info_builds_connectable_device_with_advertised_port():
    device = dircon_device_from_service_info("fallback", FakeServiceInfo())

    assert device is not None
    assert device.name == "QZ-Wahoo._wahoo-fitness-tnp._tcp.local"
    assert device.host == "192.168.1.42"
    assert device.port == 41000
    assert device.serial_number == "QZ123"
    assert device.mac_address == "AA:BB:CC:DD:EE:FF"
    assert device.source_id == "qz-dircon:192.168.1.42:41000:QZ123"
    assert device.service_uuids == [
        "00001826-0000-1000-8000-00805f9b34fb",
        "00001818-0000-1000-8000-00805f9b34fb",
    ]


def test_dircon_request_encoding_uses_qz_header_layout():
    request = encode_dircon_request(DIRCON_DISCOVER_SERVICES, 7)

    assert request == bytes((1, DIRCON_DISCOVER_SERVICES, 7, 0, 0, 0))


def test_dircon_enable_notify_request_contains_uuid_and_enable_byte():
    request = encode_dircon_request(
        DIRCON_ENABLE_NOTIFICATIONS,
        4,
        uuid16=POWER_MEASUREMENT,
        additional_data=b"\x01",
    )

    assert request[:DIRCON_HEADER_LENGTH] == bytes((1, DIRCON_ENABLE_NOTIFICATIONS, 4, 0, 0, 17))
    assert request[DIRCON_HEADER_LENGTH:DIRCON_HEADER_LENGTH + 16] == uuid_bytes(POWER_MEASUREMENT)
    assert request[-1] == 1


def test_dircon_frame_decoder_handles_split_and_coalesced_packets():
    heart_frame = _frame(DIRCON_NOTIFICATION, 1, uuid_bytes(HR_MEASUREMENT) + b"\x00\x91")
    csc_frame = _frame(DIRCON_NOTIFICATION, 2, uuid_bytes(CSC_MEASUREMENT) + b"\x02\x10\x00\x00\x10")

    packets, remainder = decode_dircon_frames(heart_frame[:8])
    assert packets == []
    assert remainder == heart_frame[:8]

    packets, remainder = decode_dircon_frames(remainder + heart_frame[8:] + csc_frame)

    assert remainder == b""
    assert len(packets) == 2
    assert packets[0].identifier == DIRCON_NOTIFICATION
    assert packets[0].uuid16 == HR_MEASUREMENT
    assert parse_dircon_notification(packets[0].uuid16, packets[0].additional_data) == {"heart_rate": 145}


def test_dircon_characteristics_response_decodes_service_characteristics_and_properties():
    payload = uuid_bytes(0x1826) + uuid_bytes(0x2AD2) + b"\x10" + uuid_bytes(0x2A37) + b"\x10"
    frame = _frame(DIRCON_DISCOVER_CHARACTERISTICS, 9, payload)

    packets, remainder = decode_dircon_frames(frame)

    assert remainder == b""
    assert packets[0].identifier == DIRCON_DISCOVER_CHARACTERISTICS
    assert packets[0].uuid16 == 0x1826
    assert packets[0].uuids == [0x2AD2, 0x2A37]
    assert packets[0].properties == [0x10, 0x10]


def test_dircon_socket_close_after_connected_is_normal_disconnect(monkeypatch):
    statuses = []

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            pass

    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, status: statuses.append(status),
        stop_event=threading.Event(),
    )

    monkeypatch.setattr("app.sensors.qz_dircon.socket.create_connection", lambda *_args, **_kwargs: FakeSocket())
    monkeypatch.setattr(client, "_discover_services", lambda _sock: [FTMS_SERVICE])
    monkeypatch.setattr(client, "_discover_characteristics", lambda _sock, _services: {FTMS_SERVICE: [HR_MEASUREMENT]})
    monkeypatch.setattr(client, "_enable_supported_notifications", lambda _sock, _characteristics: [HR_MEASUREMENT])
    monkeypatch.setattr(
        client,
        "_read_notifications",
        lambda _sock: (_ for _ in ()).throw(ConnectionError("QZ DIRCON socket closed")),
    )

    client.run()

    assert any(status.startswith("Connected QZ DIRCON") for status in statuses)
    assert "Disconnected" in statuses
    assert not any(status.startswith("Error") for status in statuses)


def test_dircon_characteristic_timeout_for_nonessential_service_does_not_abort(monkeypatch):
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, _status: None,
        stop_event=threading.Event(),
    )
    requested_services = []

    def fake_send_request(_sock, _identifier, *, uuid16=None, additional_data=b""):
        requested_services.append(uuid16)
        return len(requested_services)

    def fake_wait_for_response(_sock, _identifier, sequence, timeout=4.0):
        service = requested_services[sequence - 1]
        if service == POWER_SERVICE:
            raise TimeoutError("slow optional service")
        return DirconPacket(
            identifier=DIRCON_DISCOVER_CHARACTERISTICS,
            sequence=sequence,
            uuid16=service,
            uuids=[FTMS_INDOOR_BIKE_DATA],
        )

    monkeypatch.setattr(client, "_send_request", fake_send_request)
    monkeypatch.setattr(client, "_wait_for_response", fake_wait_for_response)

    characteristics = client._discover_characteristics(object(), [POWER_SERVICE, FTMS_SERVICE])

    assert characteristics == {FTMS_SERVICE: [FTMS_INDOOR_BIKE_DATA]}


def test_dircon_preconnect_error_is_not_masked_by_disconnected(monkeypatch):
    statuses = []
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, status: statuses.append(status),
        stop_event=threading.Event(),
    )

    def fail_connect(*_args, **_kwargs):
        raise TimeoutError("connect timed out")

    monkeypatch.setattr("app.sensors.qz_dircon.socket.create_connection", fail_connect)

    client.run()

    assert statuses[-1] == "Error: connect timed out"
    assert "Disconnected" not in statuses


def test_cadence_retained_when_power_zero_but_crank_advances(monkeypatch):
    """Cadence must NOT be zeroed when power=0 if crank revs are still advancing."""
    from app.sensors.ble_parsers import PowerMeasurement
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, _status: None,
        stop_event=threading.Event(),
    )

    # First packet establishes the crank state (no cadence returned yet)
    m0 = PowerMeasurement(power=100, has_crank_data=True, crank_revs=100, crank_event_time=1000)
    # Second packet with power=0 but crank still advancing: revs 100→101, time 1000→1024 (~60rpm)
    m1 = PowerMeasurement(power=0, has_crank_data=True, crank_revs=101, crank_event_time=1024)

    import app.sensors.qz_dircon as qz_dircon_module

    with monkeypatch.context() as mp:
        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m0)
        client._parse_notification(POWER_MEASUREMENT, b"x")

        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m1)
        values = client._parse_notification(POWER_MEASUREMENT, b"x")

    assert values.get("cadence") is not None
    assert values["cadence"] > 0


def test_cadence_zeroed_after_2s_without_crank_data(monkeypatch):
    """Cadence must go to 0 after >2 seconds without advancing crank revs."""
    from app.sensors.ble_parsers import PowerMeasurement
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, _status: None,
        stop_event=threading.Event(),
    )

    # Establish cadence first with two packets
    m0 = PowerMeasurement(power=100, has_crank_data=True, crank_revs=100, crank_event_time=1000)
    m1 = PowerMeasurement(power=100, has_crank_data=True, crank_revs=101, crank_event_time=1024)
    m2 = PowerMeasurement(power=50, has_crank_data=False)

    import app.sensors.qz_dircon as qz_dircon_module
    import time

    with monkeypatch.context() as mp:
        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m0)
        client._parse_notification(POWER_MEASUREMENT, b"x")

        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m1)
        client._parse_notification(POWER_MEASUREMENT, b"x")

        # Simulate 2.1 seconds passing
        client._cadence_seen_at = time.monotonic() - 2.1

        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m2)
        values = client._parse_notification(POWER_MEASUREMENT, b"x")
        assert "cadence" not in values


def test_cadence_immediate_zero_when_crank_revs_zero():
    """Cadence must be 0 when crank revs are explicitly 0."""
    from app.sensors.ble_parsers import CscMeasurement
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, _status: None,
        stop_event=threading.Event(),
    )

    import app.sensors.qz_dircon as qz_dircon_module
    # First packet establishes state with some revs
    m0 = CscMeasurement(has_crank_data=True, crank_revs=100, crank_event_time=1000)
    # Second packet with crank_revs=0
    m1 = CscMeasurement(has_crank_data=True, crank_revs=0, crank_event_time=1000)

    old_parse = qz_dircon_module.parse_csc_measurement
    def fake_parse(payload):
        if not hasattr(fake_parse, "call_count"):
            fake_parse.call_count = 0
        fake_parse.call_count += 1
        return m0 if fake_parse.call_count == 1 else m1

    qz_dircon_module.parse_csc_measurement = fake_parse
    try:
        client._parse_notification(CSC_MEASUREMENT, b"x")  # establishes state
        values = client._parse_notification(CSC_MEASUREMENT, b"x")  # crank_revs=0
        assert values.get("cadence") == 0
    finally:
        qz_dircon_module.parse_csc_measurement = old_parse


def test_cadence_not_zeroed_by_power_zero_alone(monkeypatch):
    """Power=0 alone must NOT force cadence to 0 if there is no crank data at all."""
    from app.sensors.ble_parsers import PowerMeasurement
    client = DirconTcpClient(
        DirconDevice(name="QZ Wahoo", host="192.168.1.42", port=36866, serial_number="QZ123"),
        data_callback=lambda _source, _values: None,
        status_callback=lambda _source, _status: None,
        stop_event=threading.Event(),
    )

    m = PowerMeasurement(power=0, has_crank_data=False)

    import app.sensors.qz_dircon as qz_dircon_module

    with monkeypatch.context() as mp:
        mp.setattr(qz_dircon_module, "parse_power_measurement", lambda _payload: m)
        values = client._parse_notification(POWER_MEASUREMENT, b"x")
        # With no prior cadence and no crank data, cadence should be absent
        assert "cadence" not in values
