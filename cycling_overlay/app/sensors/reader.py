import logging
import time
from collections import deque

from app.core.events import EventLoop
from app.core.events import Signal
from app.models.sensor_data import SensorData
from app.sensors.ble_worker import BleWorker
from app.sensors.qz_mqtt import QzMqttWorker
from app.sensors.qz_wifi import QzWifiWorker
from app.sensors.qz_wifi import QZ_DIRCON_SERVICE_TYPE
from app.sensors.qz_wifi import QZ_WIFI_SOURCE_ID
from app.sensors.qz_wifi import QZ_WEBSOCKET_SERVICE_TYPE
from app.sensors.qz_websocket import QzWebSocketWorker
from app.sensors.scanner import ScannedDevice, SERVICE_LABELS

logger = logging.getLogger(__name__)

CONNECT_QUEUE_DELAY_MS = 750
CONNECT_ATTEMPT_TIMEOUT_MS = 35000
NETWORK_CONNECT_ATTEMPT_TIMEOUT_MS = 35000
TERMINAL_STATUSES = ("Error", "Disconnected")


class SensorReader:
    def __init__(self) -> None:
        self.sensor_data_updated = Signal(object)
        self.scan_device_found = Signal(object)
        self.network_device_found = Signal(object)
        self.scan_complete = Signal()
        self.connection_status_changed = Signal(str, str)
        self.device_connected = Signal(str, str)
        self.device_disconnected = Signal(str)
        self.qz_connection_status_changed = Signal(str)

        self._worker = BleWorker()
        self._qz_wifi_worker = QzWifiWorker()
        self._qz_worker = QzWebSocketWorker()
        self._qz_mqtt_worker = QzMqttWorker()
        self._current_power: int | None = None
        self._current_cadence: int | None = None
        self._current_heart_rate: int | None = None
        self._source_values: dict[str, dict[str, int]] = {}
        self._source_metric_seen_at: dict[tuple[str, str], float] = {}
        self._connected_devices: dict[str, str] = {}
        self._connecting_devices: set[str] = set()
        self._network_connecting_devices: set[str] = set()
        self._network_connect_attempt_timers: dict[str, str | None] = {}
        self._pending_device_services: dict[str, str] = {}
        self._device_details: dict[str, dict[str, str]] = {}
        self._connect_queue: deque[tuple[str, str, dict | None]] = deque()
        self._queued_addresses: set[str] = set()
        self._active_connect_address: str | None = None
        self._connect_queue_timer: str | None = None
        self._connect_attempt_timer: str | None = None
        self._pending_scan = False

        self._worker.sensor_data_changed.connect(self._on_sensor_data)
        self._worker.scan_result.connect(self._on_scan_result)
        self._worker.scan_finished.connect(self._on_scan_finished)
        self._worker.connection_status.connect(self._on_connection_status)
        self._qz_worker.sensor_data_changed.connect(self._on_sensor_data)
        self._qz_worker.connection_status.connect(self._on_qz_connection_status)
        self._qz_wifi_worker.sensor_data_changed.connect(self._on_sensor_data)
        self._qz_wifi_worker.connection_status.connect(self._on_qz_connection_status)
        self._qz_wifi_worker.device_found.connect(self._on_network_device_found)
        self._qz_mqtt_worker.sensor_data_changed.connect(self._on_sensor_data)
        self._qz_mqtt_worker.connection_status.connect(self._on_qz_connection_status)

    def start(self) -> None:
        self._ensure_worker_started()

    def stop(self) -> None:
        if self._connect_queue_timer:
            EventLoop.get().cancel(self._connect_queue_timer)
            self._connect_queue_timer = None
        if self._connect_attempt_timer:
            EventLoop.get().cancel(self._connect_attempt_timer)
            self._connect_attempt_timer = None
        for timer_id in list(self._network_connect_attempt_timers.values()):
            EventLoop.get().cancel(timer_id)
        self._network_connect_attempt_timers.clear()
        self._connect_queue.clear()
        self._queued_addresses.clear()
        self._active_connect_address = None
        self._pending_scan = False
        self._worker.stop()
        self._qz_wifi_worker.stop()
        self._qz_worker.stop()
        self._qz_mqtt_worker.stop()
        self._connected_devices.clear()
        self._connecting_devices.clear()
        self._network_connecting_devices.clear()
        self._pending_device_services.clear()
        self._source_values.clear()
        self._source_metric_seen_at.clear()
        self._emit_aggregate()

    def connect_qz_websocket(self, host: str, port: int, auto_reconnect: bool = True) -> None:
        self._qz_worker.start(host, port, auto_reconnect)

    def disconnect_qz_websocket(self) -> None:
        self._qz_worker.stop()

    def connect_qz_mqtt(
        self,
        host: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        device: str = "+",
    ) -> None:
        self._qz_mqtt_worker.start(host, port, username, password, device)

    def disconnect_qz_mqtt(self) -> None:
        self._qz_mqtt_worker.stop()

    def scan_qz_wifi(self) -> None:
        self._qz_wifi_worker.start_auto_scan()

    def connect_network_device(self, address: str, service: str, device_info: dict | None = None) -> None:
        if service == QZ_DIRCON_SERVICE_TYPE:
            if (
                not address
                or address in self._connected_devices
                or address in self._network_connecting_devices
            ):
                return
            self._switch_active_network_device(address)
            if isinstance(device_info, dict):
                self._device_details[address] = dict(device_info)
            self._network_connecting_devices.add(address)
            self.connection_status_changed.emit(address, "Queued...")
            self._schedule_network_connect_attempt_timeout(address)
            self._qz_wifi_worker.connect_dircon(device_info or {"address": address})
        elif service == QZ_WEBSOCKET_SERVICE_TYPE:
            if (
                not address
                or address in self._connected_devices
                or address in self._network_connecting_devices
            ):
                return
            self._switch_active_network_device(address)
            if isinstance(device_info, dict):
                self._device_details[address] = dict(device_info)
            self._network_connecting_devices.add(address)
            self.connection_status_changed.emit(address, "Queued...")
            self._schedule_network_connect_attempt_timeout(address)
            self._qz_wifi_worker.connect_qz_websocket(device_info or {"address": address})

    def connect_qz_dircon_manual(self, host: str, port: int | str) -> None:
        self._qz_wifi_worker.connect_manual_dircon(host, port)

    def disconnect_qz_wifi(self) -> None:
        self._qz_wifi_worker.stop()

    def disconnect_network_device(self, address: str) -> None:
        if address.startswith(("qz-dircon:", "qz-ws:")):
            self._network_connecting_devices.discard(address)
            self._cancel_network_connect_attempt_timeout(address)
            self._connected_devices.pop(address, None)
            self._qz_wifi_worker.stop()
            self._remove_source(address)
            self.connection_status_changed.emit(address, "Disconnected")
            self.device_disconnected.emit(address)

    def scan(self) -> None:
        self._ensure_worker_started()
        if self._active_connect_address is not None or self._connect_queue:
            self._pending_scan = True
            self.connection_status_changed.emit("scanner", "Scan queued until BLE is idle")
            return
        self._worker.request_scan()

    def connect_device(self, address: str, service: str, device_info: dict | None = None) -> None:
        if (
            not address
            or address in self._connected_devices
            or address in self._connecting_devices
            or address in self._queued_addresses
        ):
            return
        self._ensure_worker_started()
        if isinstance(device_info, dict):
            self._device_details[address] = dict(device_info)
        else:
            self._device_details[address] = {"address": address, "service_type": service}
        self._connecting_devices.add(address)
        self._pending_device_services[address] = service
        self._connect_queue.append((address, service, self._device_details.get(address)))
        self._queued_addresses.add(address)
        self.connection_status_changed.emit(address, "Queued...")
        self._drain_connect_queue()

    def _ensure_worker_started(self) -> None:
        if not self._worker._running:
            self._worker.start()

    def disconnect_device(self, address: str) -> None:
        self._connecting_devices.discard(address)
        self._connected_devices.pop(address, None)
        self._pending_device_services.pop(address, None)
        self._device_details.pop(address, None)
        self._remove_queued_address(address)
        self._remove_source(address)
        self._worker.request_disconnect(address)

    @property
    def current_sensor_data(self) -> SensorData:
        return SensorData(
            power=self._current_power,
            cadence=self._current_cadence,
            heart_rate=self._current_heart_rate,
        )

    def _on_sensor_data(self, source_id, data: dict) -> None:
        if not isinstance(data, dict):
            return
        source = self._normalise_source_id(str(source_id or "unknown"))
        values = self._source_values.setdefault(source, {})
        now = time.monotonic()
        for key in ("power", "cadence", "heart_rate"):
            if key not in data:
                continue
            value = data[key]
            if value is None:
                values.pop(key, None)
                self._source_metric_seen_at.pop((source, key), None)
            else:
                values[key] = int(value)
                self._source_metric_seen_at[(source, key)] = now
        if not values:
            self._source_values.pop(source, None)
        self._emit_aggregate()

    def _on_scan_result(self, address: str, name: str, services: list) -> None:
        device = ScannedDevice(
            address=address,
            name=name,
            services=services,
        )
        device.service_type = device.detect_service_type()
        self._device_details[address] = {
            "address": device.address,
            "name": device.name or "",
            "service_type": device.service_type,
            "compatibility_hint": device.compatibility_hint or "",
            "compatibility_profile": device.compatibility_profile or "",
        }
        self.scan_device_found.emit(device)

    def _on_scan_finished(self) -> None:
        self.scan_complete.emit()

    def _on_network_device_found(self, device) -> None:
        self._device_details[device.address] = {
            "address": device.address,
            "name": device.name or "",
            "service_type": device.service_type,
            "compatibility_hint": device.compatibility_hint or "",
            "compatibility_profile": device.compatibility_profile or "",
            "host": device.host,
            "port": str(device.port),
            "serial_number": device.serial_number or "",
            "mac_address": device.mac_address or "",
            "source_type": device.source_type,
        }
        self.network_device_found.emit(device)

    def _on_connection_status(self, address: str, status: str) -> None:
        self.connection_status_changed.emit(address, status)
        if status == "Connected":
            self._finish_connect_attempt(address)
            self._connecting_devices.discard(address)
            service = self._pending_device_services.pop(address, None)
            if service is None:
                details = self._device_details.get(address, {})
                service = str(details.get("service_type", "unknown"))
            self._connected_devices[address] = service
            self.device_connected.emit(address, SERVICE_LABELS.get(service, service))
        elif status.startswith("Error") or status == "Disconnected":
            self._finish_connect_attempt(address)
            self._connecting_devices.discard(address)
            self._connected_devices.pop(address, None)
            self._pending_device_services.pop(address, None)
            self._device_details.pop(address, None)
            self._remove_source(address)
            self.device_disconnected.emit(address)

    def _on_qz_connection_status(self, address: str, status: str) -> None:
        self.qz_connection_status_changed.emit(status)
        if address != QZ_WIFI_SOURCE_ID:
            device_status = self._normalise_connection_status(status)
            self.connection_status_changed.emit(address, device_status)
            if device_status == "Connected":
                self._network_connecting_devices.discard(address)
                self._cancel_network_connect_attempt_timeout(address)
                service = self._network_service_for_address(address)
                self._connected_devices[address] = service
                self.device_connected.emit(address, self._network_service_label(service))
            elif device_status.startswith("Error") or device_status == "Disconnected":
                self._network_connecting_devices.discard(address)
                self._cancel_network_connect_attempt_timeout(address)
        if status.startswith("Error") or status == "Disconnected":
            self._remove_source(address)
            if address != QZ_WIFI_SOURCE_ID:
                self._connected_devices.pop(address, None)
                self.device_disconnected.emit(address)

    def _normalise_connection_status(self, status: str) -> str:
        if status.startswith("Connected"):
            return "Connected"
        if status.startswith("Connecting"):
            return "Connecting..."
        if status.startswith("Queued"):
            return "Queued..."
        return status

    def _network_service_for_address(self, address: str) -> str:
        details = self._device_details.get(address, {})
        service = str(details.get("service_type") or "")
        if service:
            return service
        if address.startswith("qz-ws:"):
            return QZ_WEBSOCKET_SERVICE_TYPE
        return QZ_DIRCON_SERVICE_TYPE

    def _network_service_label(self, service: str) -> str:
        if service == QZ_WEBSOCKET_SERVICE_TYPE:
            return "QZ Wi-Fi / Android app"
        return "QZ Wi-Fi / Wahoo DIRCON"

    def _switch_active_network_device(self, address: str) -> None:
        for connected_address in list(self._connected_devices):
            if connected_address == address:
                continue
            if connected_address.startswith(("qz-dircon:", "qz-ws:")):
                self.disconnect_network_device(connected_address)

    def _schedule_network_connect_attempt_timeout(self, address: str) -> None:
        self._cancel_network_connect_attempt_timeout(address)

        def on_timeout() -> None:
            self._network_connect_attempt_timers.pop(address, None)
            if address not in self._network_connecting_devices:
                return
            self.connection_status_changed.emit(address, "Error: QZ Wi-Fi connection timed out")
            self._network_connecting_devices.discard(address)
            self._connected_devices.pop(address, None)
            self._qz_wifi_worker.stop()
            self._remove_source(address)
            self.device_disconnected.emit(address)

        timer_id = EventLoop.get().call_later(NETWORK_CONNECT_ATTEMPT_TIMEOUT_MS, on_timeout)
        self._network_connect_attempt_timers[address] = timer_id

    def _cancel_network_connect_attempt_timeout(self, address: str) -> None:
        timer_id = self._network_connect_attempt_timers.pop(address, None)
        EventLoop.get().cancel(timer_id)

    def _drain_connect_queue(self) -> None:
        if self._active_connect_address is not None:
            if self._active_connect_address not in self._connecting_devices:
                self._active_connect_address = None
            else:
                return
        while self._connect_queue:
            address, service, device_info = self._connect_queue.popleft()
            self._queued_addresses.discard(address)
            if address in self._connected_devices or address not in self._connecting_devices:
                continue
            self._active_connect_address = address
            self.connection_status_changed.emit(address, "Connecting...")
            self._schedule_connect_attempt_timeout(address)
            scheduled = self._worker.request_connect(address, service, device_info)
            if scheduled is False:
                self.connection_status_changed.emit(address, "Error: BLE worker unavailable")
                self._connecting_devices.discard(address)
                self._pending_device_services.pop(address, None)
                self._remove_source(address)
                self._finish_connect_attempt(address)
                continue
            return

    def _finish_connect_attempt(self, address: str) -> None:
        if self._active_connect_address == address:
            if self._connect_attempt_timer:
                EventLoop.get().cancel(self._connect_attempt_timer)
                self._connect_attempt_timer = None
            self._active_connect_address = None
            self._schedule_connect_queue()

    def _schedule_connect_attempt_timeout(self, address: str) -> None:
        if self._connect_attempt_timer:
            EventLoop.get().cancel(self._connect_attempt_timer)
            self._connect_attempt_timer = None

        def on_timeout() -> None:
            self._connect_attempt_timer = None
            if self._active_connect_address != address:
                return
            self.connection_status_changed.emit(address, "Error: BLE connection timed out")
            self._connecting_devices.discard(address)
            self._pending_device_services.pop(address, None)
            self._worker.request_disconnect(address)
            self._remove_source(address)
            self._finish_connect_attempt(address)

        self._connect_attempt_timer = EventLoop.get().call_later(CONNECT_ATTEMPT_TIMEOUT_MS, on_timeout)

    def _schedule_connect_queue(self) -> None:
        if self._connect_queue_timer:
            return

        def run_next() -> None:
            self._connect_queue_timer = None
            if self._pending_scan and not self._connect_queue and self._active_connect_address is None:
                self._pending_scan = False
                self._worker.request_scan()
                return
            self._drain_connect_queue()

        self._connect_queue_timer = EventLoop.get().call_later(CONNECT_QUEUE_DELAY_MS, run_next)

    def _remove_queued_address(self, address: str) -> None:
        if address not in self._queued_addresses:
            return
        self._connect_queue = deque(
            (queued_address, service, info)
            for queued_address, service, info in self._connect_queue
            if queued_address != address
        )
        self._queued_addresses.discard(address)

    def _remove_source(self, source: str) -> None:
        source_ids = {str(source), self._normalise_source_id(str(source))}
        removed = False
        for source_id in source_ids:
            removed = self._source_values.pop(source_id, None) is not None or removed
        for key in list(self._source_metric_seen_at):
            if key[0] in source_ids:
                self._source_metric_seen_at.pop(key, None)
                removed = True
        if removed:
            self._emit_aggregate()

    def _normalise_source_id(self, source: str) -> str:
        if source.startswith(("ble:", "qz-", "qz_", "proform-")):
            return source
        if ":" in source:
            return f"ble:{source}"
        return source

    def _emit_aggregate(self) -> None:
        self._current_power = self._latest_metric("power")
        self._current_cadence = self._latest_metric("cadence")
        self._current_heart_rate = self._latest_metric("heart_rate")
        self.sensor_data_updated.emit(self.current_sensor_data)

    def _latest_metric(self, metric: str) -> int | None:
        best_value: int | None = None
        best_seen = -1.0
        for source, values in self._source_values.items():
            if metric not in values:
                continue
            seen_at = self._source_metric_seen_at.get((source, metric), 0.0)
            if seen_at >= best_seen:
                best_seen = seen_at
                best_value = values[metric]
        return best_value
