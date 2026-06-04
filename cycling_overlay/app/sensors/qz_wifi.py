from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.events import Signal
from app.sensors.qz_dircon import DirconDevice
from app.sensors.qz_dircon import DirconMdnsScanner
from app.sensors.qz_dircon import DirconTcpClient
from app.sensors.qz_dircon import is_zeroconf_available
from app.sensors.qz_websocket import DEFAULT_QZ_WS_PORT
from app.sensors.qz_websocket import parse_qz_workout_event

logger = logging.getLogger(__name__)

QZ_WIFI_SOURCE_ID = "qz_wifi"
PROFORM_WEBSOCKET_PATH = "/control"
PROFORM_TELNET_PORT = 23
PROFORM_WEBSOCKET_PORT = 80
SCAN_CONNECT_TIMEOUT_SECONDS = 0.25
QZ_DIRCON_SERVICE_TYPE = "qz_dircon"


@dataclass(frozen=True)
class NetworkSensorDevice:
    address: str
    name: str
    service_type: str
    host: str
    port: int
    source_type: str
    serial_number: str = ""
    mac_address: str = ""
    services: list[str] = field(default_factory=list)
    compatibility_hint: str = ""
    compatibility_profile: str = ""

    @classmethod
    def from_dircon(cls, device: DirconDevice) -> "NetworkSensorDevice":
        return cls(
            address=device.source_id,
            name=device.name or "QZ DIRCON",
            service_type=QZ_DIRCON_SERVICE_TYPE,
            host=device.host,
            port=device.port,
            source_type=QZ_DIRCON_SERVICE_TYPE,
            serial_number=device.serial_number,
            mac_address=device.mac_address,
            services=list(device.service_uuids),
            compatibility_hint="QZ Wi-Fi / Wahoo DIRCON",
            compatibility_profile="qz_dircon",
        )

    @property
    def display_name(self) -> str:
        return self.name or self.address

    def detect_service_type(self) -> str:
        return self.service_type


def parse_proform_control_event(payload: str | bytes | dict[str, Any]) -> dict[str, int]:
    if isinstance(payload, (str, bytes)):
        try:
            message = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return {}
    elif isinstance(payload, dict):
        message = payload
    else:
        return {}

    values = message.get("values") if isinstance(message.get("values"), dict) else message
    result: dict[str, int] = {}
    rpm = _first_number(values, ("RPM", "Cur RPM", "Current RPM"))
    watts = _first_number(values, ("Current Watts", "Watt attuali", "Watts", "Watt"))
    heart = _first_number(values, ("Heart Rate", "HR", "Heart"))

    if rpm is not None:
        result["cadence"] = round(rpm)
    if watts is not None:
        result["power"] = round(watts)
    if heart is not None:
        result["heart_rate"] = round(heart)
    return result


def parse_proform_telnet_metrics(text: str | bytes) -> dict[str, int]:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")

    result: dict[str, int] = {}
    watts = _regex_number(text, r"(?:Current Watts|Watts)\s*[:=]?\s*(-?\d+(?:\.\d+)?)")
    rpm = _regex_number(text, r"(?:Cur RPM|RPM)\s*[:=]?\s*(-?\d+(?:\.\d+)?)")
    heart = _regex_number(text, r"(?:Heart Rate|HR|Heart)\s*[:=]?\s*(-?\d+(?:\.\d+)?)")
    if watts is not None:
        result["power"] = round(watts)
    if rpm is not None:
        result["cadence"] = round(rpm)
    if heart is not None:
        result["heart_rate"] = round(heart)
    return result


def _first_number(values: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in values or values[key] is None:
            continue
        try:
            return float(values[key])
        except (TypeError, ValueError):
            continue
    return None


def _regex_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


class NetworkDeviceScanner:
    def local_subnet_hosts(self) -> list[str]:
        ip = self._local_ip()
        if not ip:
            return []
        network = ipaddress.ip_network(f"{ip}/24", strict=False)
        return [str(host) for host in network.hosts() if str(host) != ip]

    def reachable_hosts(self, ports: tuple[int, ...] = (PROFORM_WEBSOCKET_PORT, PROFORM_TELNET_PORT)) -> list[str]:
        found: list[str] = []
        for host in self.local_subnet_hosts():
            if any(self._is_port_open(host, port) for port in ports):
                found.append(host)
        return found

    def _local_ip(self) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
        except OSError:
            return ""
        finally:
            sock.close()

    def _is_port_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=SCAN_CONNECT_TIMEOUT_SECONDS):
                return True
        except OSError:
            return False


class QzWifiWorker:
    def __init__(self) -> None:
        self.sensor_data_changed = Signal(str, object)
        self.connection_status = Signal(str, str)
        self.device_found = Signal(object)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._app = None
        self._dircon_client: DirconTcpClient | None = None
        self._dircon_devices: dict[str, DirconDevice] = {}
        self._pending_dircon_device: DirconDevice | None = None
        self._thread_lock = threading.Lock()

    def start_auto_scan(self) -> None:
        self.start_discovery()

    def start_discovery(self) -> None:
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_discovery, daemon=True)
            self._thread.start()

    def connect_dircon(self, details: dict[str, Any] | DirconDevice) -> None:
        device = details if isinstance(details, DirconDevice) else self._dircon_device_from_details(details)
        if device is None:
            self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "Error: QZ DIRCON host/porta inválidos")
            return
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                self._pending_dircon_device = device
                self.connection_status.emit_safe(device.source_id, "Queued...")
                self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "QZ Wi-Fi ocupado; conexão enfileirada")
                return
            self._start_dircon_thread_locked(device)

    def connect_manual_dircon(self, host: str, port: int | str) -> None:
        try:
            parsed_port = int(port)
        except (TypeError, ValueError):
            self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "Error: porta DIRCON inválida")
            return
        self.connect_dircon(
            DirconDevice(
                name=f"QZ DIRCON {host}:{parsed_port}",
                host=str(host).strip(),
                port=parsed_port,
            )
        )

    def stop(self) -> None:
        self._stop_event.set()
        app = self._app
        if app is not None:
            try:
                app.close()
            except Exception:
                pass
        dircon_client = self._dircon_client
        if dircon_client is not None:
            dircon_client.close()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._app = None
        self._dircon_client = None
        self._pending_dircon_device = None
        self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "Disconnected")

    def _start_dircon_thread_locked(self, device: DirconDevice) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_dircon_client, args=(device,), daemon=True)
        self._thread.start()

    def _run_discovery(self) -> None:
        try:
            self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "Scanning QZ DIRCON/Wi-Fi devices...")
            if not is_zeroconf_available():
                self.connection_status.emit_safe(
                    QZ_WIFI_SOURCE_ID,
                    "QZ Wi-Fi indisponível: zeroconf não instalado",
                )
                return

            try:
                devices = DirconMdnsScanner().discover()
            except Exception as exc:
                logger.warning("QZ DIRCON mDNS discovery failed: %s", exc)
                self.connection_status.emit_safe(
                    QZ_WIFI_SOURCE_ID,
                    f"QZ Wi-Fi erro na descoberta mDNS: {exc}",
                )
                return
            if devices:
                for device in devices:
                    if self._stop_event.is_set():
                        return
                    self._dircon_devices[device.source_id] = device
                    self.device_found.emit_safe(NetworkSensorDevice.from_dircon(device))
                self.connection_status.emit_safe(
                    QZ_WIFI_SOURCE_ID,
                    f"QZ DIRCON encontrado: {len(devices)} fonte(s) disponível(is)",
                )
                return

            self.connection_status.emit_safe(
                QZ_WIFI_SOURCE_ID,
                "mDNS não encontrou QZ; verifique mesma rede/firewall/DIRCON ativo",
            )
        finally:
            self._start_pending_dircon_if_needed()

    def _run_auto_scan(self) -> None:
        self._run_discovery()
        if self._stop_event.is_set():
            return

        scanner = NetworkDeviceScanner()
        for host in self._qz_websocket_hosts(scanner):
            if self._stop_event.is_set():
                return
            if self._try_qz_websocket(host):
                return

        self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "Scanning direct equipment Wi-Fi...")
        for host in scanner.reachable_hosts():
            if self._stop_event.is_set():
                return
            if self._try_proform_websocket(host):
                return
            if self._try_proform_telnet(host):
                return
        if not self._stop_event.is_set():
            self.connection_status.emit_safe(QZ_WIFI_SOURCE_ID, "No compatible QZ/Wi-Fi device found")

    def _run_dircon_client(self, device: DirconDevice) -> None:
        try:
            self._dircon_devices[device.source_id] = device
            self._try_qz_dircon(device)
        finally:
            with self._thread_lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _start_pending_dircon_if_needed(self) -> None:
        with self._thread_lock:
            pending = self._pending_dircon_device
            self._pending_dircon_device = None
            if self._thread is threading.current_thread():
                self._thread = None
            if pending is None or self._stop_event.is_set():
                return
            self._start_dircon_thread_locked(pending)

    def _dircon_device_from_details(self, details: dict[str, Any]) -> DirconDevice | None:
        source_id = str(details.get("source_id") or details.get("address") or "")
        if source_id in self._dircon_devices:
            return self._dircon_devices[source_id]
        host = str(details.get("host") or "").strip()
        if not host:
            return None
        try:
            port = int(details.get("port") or 0)
        except (TypeError, ValueError):
            return None
        if port <= 0:
            return None
        return DirconDevice(
            name=str(details.get("name") or f"QZ DIRCON {host}:{port}"),
            host=host,
            port=port,
            serial_number=str(details.get("serial_number") or ""),
            mac_address=str(details.get("mac_address") or ""),
            service_uuids=list(details.get("services") or []),
        )

    def _qz_websocket_hosts(self, scanner: NetworkDeviceScanner) -> list[str]:
        hosts = ["127.0.0.1", "localhost"]
        for host in scanner.reachable_hosts((DEFAULT_QZ_WS_PORT,)):
            if host not in hosts:
                hosts.append(host)
        return hosts

    def _try_qz_dircon(self, device: DirconDevice) -> bool:
        connected = False

        def on_status(source_id: str, status: str) -> None:
            nonlocal connected
            if status.startswith("Connected"):
                connected = True
            self.connection_status.emit_safe(source_id, status)

        client = DirconTcpClient(
            device,
            data_callback=lambda source_id, values: self.sensor_data_changed.emit_safe(source_id, values),
            status_callback=on_status,
            stop_event=self._stop_event,
        )
        self._dircon_client = client
        client.run()
        self._dircon_client = None
        return connected

    def _try_qz_websocket(self, host: str) -> bool:
        try:
            import websocket
        except ImportError:
            self.connection_status.emit_safe(
                QZ_WIFI_SOURCE_ID,
                "Error: websocket-client dependency is not installed",
            )
            return False

        url = f"ws://{host}:{DEFAULT_QZ_WS_PORT}"
        source_id = f"qz-ws:{host}:{DEFAULT_QZ_WS_PORT}"
        connected = False
        self.connection_status.emit_safe(source_id, f"Connecting QZ WebSocket {host}:{DEFAULT_QZ_WS_PORT}")

        def on_open(_app) -> None:
            nonlocal connected
            connected = True
            self.connection_status.emit_safe(source_id, f"Connected QZ WebSocket {host}")

        def on_message(_app, message) -> None:
            values = parse_qz_workout_event(message)
            if values:
                self.sensor_data_changed.emit_safe(source_id, values)
            if values.get("power") is None and values.get("cadence") is None and values.get("heart_rate") is None:
                self.connection_status.emit_safe(source_id, "Disconnected")

        def on_error(_app, error) -> None:
            if connected and not self._stop_event.is_set():
                logger.warning("QZ WebSocket error for %s: %s", host, error)
                self.connection_status.emit_safe(source_id, f"Error: {error}")

        def on_close(_app, *_args) -> None:
            if connected and not self._stop_event.is_set():
                self.connection_status.emit_safe(source_id, "Disconnected")

        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2.0)
        try:
            app = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            self._app = app
            app.run_forever()
        finally:
            socket.setdefaulttimeout(old_timeout)
            self._app = None
        return connected

    def _try_proform_websocket(self, host: str) -> bool:
        try:
            import websocket
        except ImportError:
            self.connection_status.emit_safe(
                QZ_WIFI_SOURCE_ID,
                "Error: websocket-client dependency is not installed",
            )
            return False

        url = f"ws://{host}:{PROFORM_WEBSOCKET_PORT}{PROFORM_WEBSOCKET_PATH}"
        source_id = f"proform-ws:{host}:{PROFORM_WEBSOCKET_PORT}"
        connected = False
        self.connection_status.emit_safe(source_id, f"Connecting ProForm WebSocket {host}")

        def on_open(_app) -> None:
            nonlocal connected
            connected = True
            self.connection_status.emit_safe(source_id, f"Connected ProForm WebSocket {host}")

        def on_message(_app, message) -> None:
            values = parse_proform_control_event(message)
            if values:
                self.sensor_data_changed.emit_safe(source_id, values)

        def on_error(_app, error) -> None:
            if connected and not self._stop_event.is_set():
                logger.warning("ProForm WebSocket error for %s: %s", host, error)
                self.connection_status.emit_safe(source_id, f"Error: {error}")

        def on_close(_app, *_args) -> None:
            if connected and not self._stop_event.is_set():
                self.connection_status.emit_safe(source_id, "Disconnected")

        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(2.0)
        try:
            app = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            self._app = app
            app.run_forever()
        finally:
            socket.setdefaulttimeout(old_timeout)
            self._app = None
        return connected

    def _try_proform_telnet(self, host: str) -> bool:
        try:
            sock = socket.create_connection((host, PROFORM_TELNET_PORT), timeout=1.0)
        except OSError:
            return False

        source_id = f"proform-telnet:{host}:{PROFORM_TELNET_PORT}"
        self.connection_status.emit_safe(source_id, f"Connected ProForm Telnet {host}")
        with sock:
            sock.settimeout(1.0)
            try:
                sock.sendall(b"./utconfig\n2\n")
            except OSError:
                return False
            while not self._stop_event.is_set():
                try:
                    chunk = sock.recv(4096)
                except OSError:
                    break
                if not chunk:
                    break
                values = parse_proform_telnet_metrics(chunk)
                if values:
                    self.sensor_data_changed.emit_safe(source_id, values)
                time.sleep(0.05)
        if not self._stop_event.is_set():
            self.connection_status.emit_safe(source_id, "Disconnected")
        return True
