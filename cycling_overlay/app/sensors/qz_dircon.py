from __future__ import annotations

import logging
import importlib.util
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from app.sensors.ble_parsers import (
    parse_csc_measurement,
    parse_ftms_indoor_bike_data,
    parse_heart_rate,
    parse_power_measurement,
)

logger = logging.getLogger(__name__)

DIRCON_CANONICAL_SERVICE_TYPE = "_wahoo-fitness-tnp._tcp.local."
DIRCON_SERVICE_TYPES = (DIRCON_CANONICAL_SERVICE_TYPE, "_wahoo-fitness-tnp._tcp.local")
DIRCON_HEADER_LENGTH = 6
DIRCON_VERSION = 1
DIRCON_DISCOVER_SERVICES = 0x01
DIRCON_DISCOVER_CHARACTERISTICS = 0x02
DIRCON_ENABLE_NOTIFICATIONS = 0x05
DIRCON_NOTIFICATION = 0x06
DIRCON_SUCCESS = 0x00

FTMS_SERVICE = 0x1826
POWER_SERVICE = 0x1818
CSC_SERVICE = 0x1816
HR_SERVICE = 0x180D
FTMS_INDOOR_BIKE_DATA = 0x2AD2
POWER_MEASUREMENT = 0x2A63
CSC_MEASUREMENT = 0x2A5B
HR_MEASUREMENT = 0x2A37

SUPPORTED_CHARACTERISTICS = {
    FTMS_INDOOR_BIKE_DATA,
    POWER_MEASUREMENT,
    CSC_MEASUREMENT,
    HR_MEASUREMENT,
}


def is_zeroconf_available() -> bool:
    return importlib.util.find_spec("zeroconf") is not None


@dataclass(frozen=True)
class DirconDevice:
    name: str
    host: str
    port: int
    serial_number: str = ""
    mac_address: str = ""
    service_uuids: list[str] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        identity = self.serial_number or self.mac_address or self.name or self.host
        return f"qz-dircon:{self.host}:{self.port}:{identity}"


@dataclass
class DirconPacket:
    identifier: int
    sequence: int
    response_code: int = DIRCON_SUCCESS
    uuid16: int | None = None
    uuids: list[int] = field(default_factory=list)
    properties: list[int] = field(default_factory=list)
    additional_data: bytes = b""


@dataclass
class CadenceState:
    revolutions: int | None = None
    event_time: int | None = None


def normalize_dircon_service_type(service_type: str) -> str:
    value = str(service_type or "").strip()
    if value == "_wahoo-fitness-tnp._tcp.local":
        return f"{value}."
    return value


def dircon_browser_service_types() -> tuple[str, ...]:
    normalized: list[str] = []
    for service_type in DIRCON_SERVICE_TYPES:
        normalized_service_type = normalize_dircon_service_type(service_type)
        if not normalized_service_type.endswith(".local."):
            logger.warning("Ignoring invalid DIRCON mDNS service type: %s", service_type)
            continue
        if normalized_service_type not in normalized:
            normalized.append(normalized_service_type)
    return tuple(normalized)


def normalize_ble_uuid(value: str | int) -> str:
    uuid16 = uuid16_from_value(value)
    return f"0000{uuid16:04x}-0000-1000-8000-00805f9b34fb"


def uuid16_from_value(value: str | int) -> int:
    if isinstance(value, int):
        return value & 0xFFFF
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("empty UUID")
    if text.startswith("0x"):
        return int(text, 16) & 0xFFFF
    if "-" in text and len(text) >= 8:
        return int(text[4:8], 16) & 0xFFFF
    return int(text[-4:], 16) & 0xFFFF


def parse_ble_service_uuids(value: str | bytes | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    services: list[str] = []
    for raw_part in str(value).replace(";", ",").split(","):
        part = raw_part.strip()
        if not part:
            continue
        try:
            services.append(normalize_ble_uuid(part))
        except ValueError:
            continue
    return services


def uuid_bytes(uuid16: int) -> bytes:
    data = bytearray(
        b"\x00\x00\x18\x26\x00\x00\x10\x00\x80\x00\x00\x80\x5f\x9b\x34\xfb"
    )
    data[2] = (uuid16 >> 8) & 0xFF
    data[3] = uuid16 & 0xFF
    return bytes(data)


def uuid16_from_bytes(data: bytes | bytearray) -> int:
    if len(data) < 4:
        raise ValueError("DIRCON UUID payload is truncated")
    return (data[2] << 8) | data[3]


def encode_dircon_request(
    identifier: int,
    sequence: int,
    *,
    uuid16: int | None = None,
    additional_data: bytes = b"",
) -> bytes:
    body = b""
    if uuid16 is not None:
        body += uuid_bytes(uuid16)
    body += additional_data
    return bytes(
        (
            DIRCON_VERSION,
            identifier & 0xFF,
            sequence & 0xFF,
            DIRCON_SUCCESS,
            (len(body) >> 8) & 0xFF,
            len(body) & 0xFF,
        )
    ) + body


def decode_dircon_frames(buffer: bytes | bytearray) -> tuple[list[DirconPacket], bytes]:
    data = bytes(buffer)
    packets: list[DirconPacket] = []
    offset = 0
    while len(data) - offset >= DIRCON_HEADER_LENGTH:
        identifier = data[offset + 1]
        sequence = data[offset + 2]
        response_code = data[offset + 3]
        length = (data[offset + 4] << 8) | data[offset + 5]
        end = offset + DIRCON_HEADER_LENGTH + length
        if len(data) < end:
            break
        payload = data[offset + DIRCON_HEADER_LENGTH:end]
        packets.append(_decode_packet(identifier, sequence, response_code, payload))
        offset = end
    return packets, data[offset:]


def _decode_packet(identifier: int, sequence: int, response_code: int, payload: bytes) -> DirconPacket:
    packet = DirconPacket(identifier=identifier, sequence=sequence, response_code=response_code)
    if response_code != DIRCON_SUCCESS:
        return packet
    if identifier == DIRCON_DISCOVER_SERVICES:
        packet.uuids = [
            uuid16_from_bytes(payload[index:index + 16])
            for index in range(0, len(payload), 16)
            if len(payload[index:index + 16]) == 16
        ]
    elif identifier == DIRCON_DISCOVER_CHARACTERISTICS and len(payload) >= 16:
        packet.uuid16 = uuid16_from_bytes(payload[:16])
        rest = payload[16:]
        for index in range(0, len(rest), 17):
            chunk = rest[index:index + 17]
            if len(chunk) != 17:
                continue
            packet.uuids.append(uuid16_from_bytes(chunk[:16]))
            packet.properties.append(chunk[16])
    elif identifier in (DIRCON_ENABLE_NOTIFICATIONS, DIRCON_NOTIFICATION) and len(payload) >= 16:
        packet.uuid16 = uuid16_from_bytes(payload[:16])
        packet.additional_data = payload[16:]
    return packet


def parse_dircon_notification(uuid16: int, payload: bytes | bytearray) -> dict[str, int]:
    if uuid16 == FTMS_INDOOR_BIKE_DATA:
        return parse_ftms_indoor_bike_data(payload).values
    if uuid16 == POWER_MEASUREMENT:
        measurement = parse_power_measurement(payload)
        result: dict[str, int] = {}
        if measurement.power is not None:
            result["power"] = measurement.power
        return result
    if uuid16 == CSC_MEASUREMENT:
        measurement = parse_csc_measurement(payload)
        return {"cadence": 0} if measurement.has_crank_data and measurement.crank_revs == 0 else {}
    if uuid16 == HR_MEASUREMENT:
        heart_rate = parse_heart_rate(payload)
        return {"heart_rate": heart_rate} if heart_rate is not None else {}
    return {}


class DirconMdnsScanner:
    def discover(self, timeout: float = 2.5) -> list[DirconDevice]:
        if not is_zeroconf_available():
            logger.info("zeroconf dependency is not installed; QZ DIRCON mDNS disabled")
            return []

        try:
            from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
        except ImportError:
            logger.info("zeroconf dependency is not installed; QZ DIRCON mDNS disabled")
            return []

        devices: dict[str, DirconDevice] = {}

        class Listener(ServiceListener):
            def add_service(self, zeroconf, service_type, name) -> None:
                info = zeroconf.get_service_info(service_type, name, timeout=int(timeout * 1000))
                if info is None:
                    return
                device = self._device_from_info(name, info)
                if device is not None:
                    devices[device.source_id] = device

            def update_service(self, zeroconf, service_type, name) -> None:
                self.add_service(zeroconf, service_type, name)

            def remove_service(self, zeroconf, service_type, name) -> None:
                return None

            def _device_from_info(self, name: str, info) -> DirconDevice | None:
                device = dircon_device_from_service_info(name, info)
                return device

        zeroconf = Zeroconf()
        try:
            listener = Listener()
            try:
                browsers = [
                    ServiceBrowser(zeroconf, service_type, listener)
                    for service_type in dircon_browser_service_types()
                ]
            except Exception as exc:
                logger.warning("QZ DIRCON mDNS discovery failed to start: %s", exc)
                return []
            time.sleep(timeout)
            for browser in browsers:
                try:
                    browser.cancel()
                except Exception:
                    pass
        finally:
            zeroconf.close()
        return list(devices.values())


def dircon_device_from_service_info(name: str, info) -> DirconDevice | None:
    host = _host_from_service_info(info)
    if not host:
        return None
    properties = {
        _decode_property_key(key): _decode_property_value(value)
        for key, value in (getattr(info, "properties", None) or {}).items()
    }
    return DirconDevice(
        name=str(getattr(info, "name", None) or name).rstrip("."),
        host=host,
        port=int(getattr(info, "port", 0) or 0),
        serial_number=properties.get("serial-number", ""),
        mac_address=properties.get("mac-address", ""),
        service_uuids=parse_ble_service_uuids(properties.get("ble-service-uuids")),
    )


def _host_from_service_info(info) -> str:
    parsed_addresses = []
    parsed = getattr(info, "parsed_addresses", None)
    if callable(parsed):
        try:
            parsed_addresses = [str(address) for address in parsed()]
        except Exception:
            parsed_addresses = []
    for address in parsed_addresses:
        if _is_ipv4(address):
            return address
    for address in parsed_addresses:
        if address:
            return address

    ipv6_host = ""
    for raw_address in getattr(info, "addresses", None) or []:
        try:
            if len(raw_address) == 4:
                return socket.inet_ntop(socket.AF_INET, raw_address)
            if len(raw_address) == 16 and not ipv6_host:
                ipv6_host = socket.inet_ntop(socket.AF_INET6, raw_address)
        except OSError:
            continue
    return ipv6_host


def _is_ipv4(address: str) -> bool:
    try:
        socket.inet_aton(address)
        return address.count(".") == 3
    except OSError:
        return False


def _decode_property_key(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def _decode_property_value(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


class DirconTcpClient:
    def __init__(
        self,
        device: DirconDevice,
        data_callback: Callable[[str, dict[str, int]], None],
        status_callback: Callable[[str, str], None],
        stop_event: threading.Event,
    ) -> None:
        self.device = device
        self.data_callback = data_callback
        self.status_callback = status_callback
        self.stop_event = stop_event
        self._sequence = 0
        self._buffer = b""
        self._socket: socket.socket | None = None
        self._power_crank_state = CadenceState()
        self._power_wheel_state = CadenceState()
        self._csc_state = CadenceState()

    def run(self) -> None:
        source_id = self.device.source_id
        connected = False
        try:
            self.status_callback(source_id, f"Connecting QZ DIRCON {self.device.host}:{self.device.port}")
            with socket.create_connection((self.device.host, self.device.port), timeout=4.0) as sock:
                self._socket = sock
                sock.settimeout(1.0)
                services = self._discover_services(sock)
                characteristics = self._discover_characteristics(sock, services)
                enabled = self._enable_supported_notifications(sock, characteristics)
                if not enabled:
                    raise RuntimeError("No supported QZ DIRCON measurement characteristic found")
                self.status_callback(source_id, f"Connected QZ DIRCON {self.device.name}")
                connected = True
                self._read_notifications(sock)
        except Exception as exc:
            if not self.stop_event.is_set():
                if connected and isinstance(exc, ConnectionError):
                    logger.info("QZ DIRCON disconnected for %s: %s", source_id, exc)
                else:
                    logger.warning("QZ DIRCON error for %s: %s", source_id, exc)
                    self.status_callback(source_id, f"Error: {exc}")
        finally:
            self._socket = None
            self.status_callback(source_id, "Disconnected")

    def close(self) -> None:
        sock = self._socket
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFF
        return self._sequence or self._next_sequence()

    def _send_request(
        self,
        sock: socket.socket,
        identifier: int,
        *,
        uuid16: int | None = None,
        additional_data: bytes = b"",
    ) -> int:
        sequence = self._next_sequence()
        sock.sendall(
            encode_dircon_request(
                identifier,
                sequence,
                uuid16=uuid16,
                additional_data=additional_data,
            )
        )
        return sequence

    def _discover_services(self, sock: socket.socket) -> list[int]:
        sequence = self._send_request(sock, DIRCON_DISCOVER_SERVICES)
        packet = self._wait_for_response(sock, DIRCON_DISCOVER_SERVICES, sequence)
        return packet.uuids

    def _discover_characteristics(self, sock: socket.socket, services: list[int]) -> dict[int, list[int]]:
        result: dict[int, list[int]] = {}
        for service in services:
            sequence = self._send_request(sock, DIRCON_DISCOVER_CHARACTERISTICS, uuid16=service)
            packet = self._wait_for_response(sock, DIRCON_DISCOVER_CHARACTERISTICS, sequence)
            result[service] = packet.uuids
        return result

    def _enable_supported_notifications(self, sock: socket.socket, characteristics: dict[int, list[int]]) -> list[int]:
        enabled: list[int] = []
        for chars in characteristics.values():
            for characteristic in chars:
                if characteristic not in SUPPORTED_CHARACTERISTICS:
                    continue
                sequence = self._send_request(
                    sock,
                    DIRCON_ENABLE_NOTIFICATIONS,
                    uuid16=characteristic,
                    additional_data=b"\x01",
                )
                try:
                    self._wait_for_response(sock, DIRCON_ENABLE_NOTIFICATIONS, sequence)
                except TimeoutError:
                    pass
                enabled.append(characteristic)
        return enabled

    def _wait_for_response(self, sock: socket.socket, identifier: int, sequence: int, timeout: float = 3.0) -> DirconPacket:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self.stop_event.is_set():
            for packet in self._read_available_packets(sock):
                if packet.identifier == DIRCON_NOTIFICATION:
                    self._handle_notification(packet)
                    continue
                if packet.identifier == identifier and packet.sequence == sequence:
                    if packet.response_code != DIRCON_SUCCESS:
                        raise RuntimeError(f"DIRCON response error {packet.response_code}")
                    return packet
        raise TimeoutError("QZ DIRCON response timed out")

    def _read_notifications(self, sock: socket.socket) -> None:
        while not self.stop_event.is_set():
            for packet in self._read_available_packets(sock):
                if packet.identifier == DIRCON_NOTIFICATION:
                    self._handle_notification(packet)

    def _read_available_packets(self, sock: socket.socket) -> list[DirconPacket]:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            return []
        if not chunk:
            raise ConnectionError("QZ DIRCON socket closed")
        self._buffer += chunk
        packets, self._buffer = decode_dircon_frames(self._buffer)
        return packets

    def _handle_notification(self, packet: DirconPacket) -> None:
        if packet.uuid16 is None:
            return
        values = self._parse_notification(packet.uuid16, packet.additional_data)
        if values:
            self.data_callback(self.device.source_id, values)

    def _parse_notification(self, uuid16: int, payload: bytes | bytearray) -> dict[str, int]:
        if uuid16 == POWER_MEASUREMENT:
            measurement = parse_power_measurement(payload)
            result: dict[str, int] = {}
            if measurement.power is not None:
                result["power"] = measurement.power
                if measurement.power <= 0:
                    result["cadence"] = 0
                    return result
            crank_rpm = None
            if measurement.has_crank_data:
                crank_rpm = _cadence_from_revolutions(
                    self._power_crank_state,
                    measurement.crank_revs,
                    measurement.crank_event_time,
                    time_scale=1024,
                    multiplier=1.0,
                )
            if crank_rpm is not None and crank_rpm > 0:
                result["cadence"] = crank_rpm
                return result
            if measurement.has_wheel_data:
                wheel_rpm = _cadence_from_revolutions(
                    self._power_wheel_state,
                    measurement.wheel_revs,
                    measurement.wheel_event_time,
                    time_scale=2048,
                    multiplier=0.5,
                )
                if wheel_rpm is not None and wheel_rpm > 0:
                    result["cadence"] = wheel_rpm
            return result
        if uuid16 == CSC_MEASUREMENT:
            measurement = parse_csc_measurement(payload)
            rpm = None
            if measurement.has_crank_data:
                rpm = _cadence_from_revolutions(
                    self._csc_state,
                    measurement.crank_revs,
                    measurement.crank_event_time,
                    time_scale=1024,
                    multiplier=1.0,
                )
            return {"cadence": rpm} if rpm is not None else {}
        return parse_dircon_notification(uuid16, payload)


def _cadence_from_revolutions(
    state: CadenceState,
    revolutions: int | None,
    event_time: int | None,
    *,
    time_scale: int,
    multiplier: float,
) -> int | None:
    if revolutions is None or event_time is None:
        return None
    previous_revolutions = state.revolutions
    previous_event_time = state.event_time
    state.revolutions = revolutions
    state.event_time = event_time
    if previous_revolutions is None or previous_event_time is None:
        return None

    delta_revolutions = revolutions - previous_revolutions
    if delta_revolutions < 0:
        delta_revolutions += 1 << 16
    delta_time = event_time - previous_event_time
    if delta_time < 0:
        delta_time += 1 << 16
    if delta_time <= 0:
        return 0 if delta_revolutions == 0 else None
    if delta_revolutions <= 0:
        return 0
    return round(delta_revolutions * time_scale * 60 * multiplier / delta_time)
