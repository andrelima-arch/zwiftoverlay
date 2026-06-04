from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from app.core.events import Signal

logger = logging.getLogger(__name__)

DEFAULT_QZ_WS_PORT = 34107


def parse_qz_workout_event(payload: str | bytes | dict[str, Any]) -> dict[str, int | None]:
    if isinstance(payload, (str, bytes)):
        try:
            message = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return {}
    elif isinstance(payload, dict):
        message = payload
    else:
        return {}

    if message.get("deviceConnected") is False:
        return {"power": None, "cadence": None, "heart_rate": None}

    result: dict[str, int | None] = {}
    watts = _first_number(message, ("watts", "power"))
    cadence = _first_number(message, ("cadence", "bikeCadence", "bike_cadence", "currentCadence"))
    heart = _first_number(message, ("heart", "heartRate", "heart_rate"))
    if watts is not None:
        result["power"] = round(watts)
    if cadence is not None:
        result["cadence"] = round(cadence)
    if heart is not None:
        result["heart_rate"] = round(heart)
    return result


def _first_number(message: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in message or message[key] is None:
            continue
        try:
            return float(message[key])
        except (TypeError, ValueError):
            continue
    return None


def _device_connected_false(payload: str | bytes | dict[str, Any]) -> bool:
    if isinstance(payload, (str, bytes)):
        try:
            message = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return False
    elif isinstance(payload, dict):
        message = payload
    else:
        return False
    return message.get("deviceConnected") is False


class QzWebSocketWorker:
    def __init__(self) -> None:
        self.sensor_data_changed = Signal(str, object)
        self.connection_status = Signal(str, str)
        self._thread: threading.Thread | None = None
        self._app = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self, host: str, port: int = DEFAULT_QZ_WS_PORT, auto_reconnect: bool = True) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(host.strip() or "127.0.0.1", int(port), bool(auto_reconnect)),
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        app = self._app
        if app is not None:
            try:
                app.close()
            except Exception:
                pass
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None
        self._app = None
        self.connection_status.emit_safe("qz_ws", "Disconnected")

    def _run(self, host: str, port: int, auto_reconnect: bool) -> None:
        while not self._stop_event.is_set():
            try:
                import websocket
            except ImportError:
                self.connection_status.emit_safe(
                    "qz_ws",
                    "Error: websocket-client dependency is not installed",
                )
                return

            url = f"ws://{host}:{port}"
            self.connection_status.emit_safe("qz_ws", f"Connecting to {url}")

            def on_open(_app) -> None:
                self.connection_status.emit_safe("qz_ws", "Connected")

            def on_message(_app, message) -> None:
                values = parse_qz_workout_event(message)
                if values:
                    self.sensor_data_changed.emit_safe("qz_ws", values)
                if _device_connected_false(message):
                    self.connection_status.emit_safe("qz_ws", "Disconnected")

            def on_error(_app, error) -> None:
                if not self._stop_event.is_set():
                    logger.warning("QZ WebSocket error: %s", error)
                    self.connection_status.emit_safe("qz_ws", f"Error: {error}")

            def on_close(_app, *_args) -> None:
                if not self._stop_event.is_set():
                    self.connection_status.emit_safe("qz_ws", "Disconnected")

            app = websocket.WebSocketApp(
                url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            self._app = app
            app.run_forever()
            self._app = None

            if not auto_reconnect or self._stop_event.is_set():
                break
            time.sleep(2.0)
