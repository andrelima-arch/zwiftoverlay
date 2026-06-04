from __future__ import annotations

import logging
import threading

from app.core.events import Signal

logger = logging.getLogger(__name__)

DEFAULT_QZ_MQTT_HOST = "127.0.0.1"
DEFAULT_QZ_MQTT_PORT = 1883
DEFAULT_QZ_MQTT_DEVICE = "+"
QZ_MQTT_SOURCE_ID = "qz_mqtt"


def parse_qz_mqtt_message(topic: str, payload: str | bytes | int | float | bool) -> dict[str, int | None]:
    topic = str(topic or "").strip().lower()
    if topic.endswith("/device/connected") or topic.endswith("/status"):
        connected = _payload_bool(payload)
        if connected is False:
            return {"power": None, "cadence": None, "heart_rate": None}
        return {}

    value = _payload_number(payload)
    if value is None:
        return {}

    if topic.endswith("/watts/current"):
        return {"power": round(value)}
    if topic.endswith("/bike/cadence/current") or topic.endswith("/cadence/current"):
        return {"cadence": round(value)}
    if topic.endswith("/heart/current"):
        return {"heart_rate": round(value)}
    return {}


def _payload_number(payload: str | bytes | int | float) -> float | None:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="ignore")
    try:
        return float(payload)
    except (TypeError, ValueError):
        return None


def _payload_bool(payload: str | bytes | int | float | bool) -> bool | None:
    if isinstance(payload, bool):
        return payload
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="ignore")
    if isinstance(payload, str):
        value = payload.strip().lower()
        if value in {"true", "1", "yes", "on", "connected", "online"}:
            return True
        if value in {"false", "0", "no", "off", "disconnected", "offline"}:
            return False
    number = _payload_number(payload)
    if number is None:
        return None
    return number != 0


class QzMqttWorker:
    def __init__(self) -> None:
        self.sensor_data_changed = Signal(str, object)
        self.connection_status = Signal(str, str)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._client = None
        self._lock = threading.Lock()

    def start(
        self,
        host: str = DEFAULT_QZ_MQTT_HOST,
        port: int = DEFAULT_QZ_MQTT_PORT,
        username: str = "",
        password: str = "",
        device: str = DEFAULT_QZ_MQTT_DEVICE,
    ) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(
                    str(host or DEFAULT_QZ_MQTT_HOST).strip(),
                    int(port or DEFAULT_QZ_MQTT_PORT),
                    str(username or ""),
                    str(password or ""),
                    str(device or DEFAULT_QZ_MQTT_DEVICE).strip() or DEFAULT_QZ_MQTT_DEVICE,
                ),
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        client = self._client
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._client = None
        self._thread = None
        self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, "Disconnected")

    def _run(self, host: str, port: int, username: str, password: str, device: str) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.connection_status.emit_safe(
                QZ_MQTT_SOURCE_ID,
                "Error: paho-mqtt dependency is not installed",
            )
            return

        try:
            client = mqtt.Client()
        except TypeError:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

        if username:
            client.username_pw_set(username, password or None)

        topics = (
            f"QZ/{device}/workout/watts/current",
            f"QZ/{device}/workout/bike/cadence/current",
            f"QZ/{device}/workout/heart/current",
            f"QZ/{device}/workout/device/connected",
            f"QZ/{device}/status",
            f"QZ/{device}/watts/current",
            f"QZ/{device}/bike/cadence/current",
            f"QZ/{device}/heart/current",
            f"QZ/{device}/device/connected",
        )

        def on_connect(_client, _userdata, _flags, rc, *_extra) -> None:
            if rc == 0:
                for topic in topics:
                    _client.subscribe(topic)
                self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, "Connected")
            else:
                self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, f"Error: MQTT connect rc={rc}")

        def on_message(_client, _userdata, message) -> None:
            values = parse_qz_mqtt_message(message.topic, message.payload)
            if values:
                self.sensor_data_changed.emit_safe(QZ_MQTT_SOURCE_ID, values)
            topic = str(message.topic or "").strip().lower()
            if (
                topic.endswith("/device/connected") or topic.endswith("/status")
            ) and _payload_bool(message.payload) is False:
                self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, "Disconnected")

        def on_disconnect(_client, _userdata, *_args) -> None:
            if not self._stop_event.is_set():
                self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, "Disconnected")

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        self._client = client
        self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, f"Connecting MQTT {host}:{port}")
        try:
            client.connect(host, port, keepalive=30)
            client.loop_forever()
        except Exception as exc:
            if not self._stop_event.is_set():
                logger.warning("QZ MQTT error: %s", exc)
                self.connection_status.emit_safe(QZ_MQTT_SOURCE_ID, f"Error: {exc}")
        finally:
            self._client = None
