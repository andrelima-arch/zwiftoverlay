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
    FTMS_SERVICE,
    HR_MEASUREMENT,
    POWER_MEASUREMENT,
    DirconDevice,
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
