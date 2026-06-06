import base64
import json
from pathlib import Path

from platformdirs import user_config_dir


APP_NAME = "cycling-overlay"
SUPPORTED_UI_LANGUAGES = {"en", "pt"}


def _encode_sensitive(value: str) -> str:
    """Obfuscate a sensitive string with base64 (not encryption, just casual protection)."""
    if not value:
        return value
    # Already encoded?
    try:
        decoded = base64.b64decode(value.encode(), validate=True).decode("utf-8")
        if decoded == value:
            # Not base64, encode it
            pass
        else:
            # It was already base64 and decoded to something different
            return value
    except Exception:
        pass
    return base64.b64encode(value.encode()).decode()


def _decode_sensitive(value: str) -> str:
    """Deobfuscate a string encoded by _encode_sensitive."""
    if not value:
        return value
    try:
        decoded = base64.b64decode(value.encode(), validate=True).decode("utf-8")
        # Simple heuristic: if decoded looks like the original or is obviously wrong, return original
        # This handles migration from plain-text values
        if len(decoded) >= len(value) / 2:
            return decoded
    except Exception:
        pass
    return value


class ConfigManager:
    def __init__(self) -> None:
        self._config_dir = Path(user_config_dir(APP_NAME))
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._config_dir / "config.json"
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if self._config_file.exists():
            try:
                self._data = json.loads(self._config_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._migrate_profile_defaults()

    def _migrate_profile_defaults(self) -> None:
        legacy_weight = self._data.get("weight_kg")
        legacy_ftp = self._data.get("ftp")
        if legacy_weight is not None and "manual_weight_kg" not in self._data:
            self._data["manual_weight_kg"] = legacy_weight
        if legacy_ftp is not None and "manual_ftp" not in self._data:
            self._data["manual_ftp"] = legacy_ftp
        if self.profile_source == "intervals_icu":
            if legacy_weight is not None and "intervals_weight_kg" not in self._data:
                self._data["intervals_weight_kg"] = legacy_weight
            if legacy_ftp is not None and "intervals_ftp" not in self._data:
                self._data["intervals_ftp"] = legacy_ftp

    def _save(self) -> None:
        self._config_file.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)

    def set(self, key: str, value: object) -> None:
        self._data[key] = value
        self._save()

    @property
    def ui_language(self) -> str:
        value = str(self._data.get("ui_language", "en"))
        return value if value in SUPPORTED_UI_LANGUAGES else "en"

    @ui_language.setter
    def ui_language(self, value: str | None) -> None:
        language = str(value or "en")
        self._data["ui_language"] = language if language in SUPPORTED_UI_LANGUAGES else "en"
        self._save()

    @property
    def weight_kg(self) -> float | None:
        val = self._data.get("weight_kg")
        return float(val) if val is not None else None

    @weight_kg.setter
    def weight_kg(self, value: float | None) -> None:
        if value is None:
            self._data.pop("weight_kg", None)
        else:
            self._data["weight_kg"] = value
        self._save()

    @property
    def manual_weight_kg(self) -> float | None:
        val = self._data.get("manual_weight_kg")
        return float(val) if val is not None else None

    @manual_weight_kg.setter
    def manual_weight_kg(self, value: float | None) -> None:
        if value is None:
            self._data.pop("manual_weight_kg", None)
        else:
            self._data["manual_weight_kg"] = value
        self._save()

    @property
    def intervals_weight_kg(self) -> float | None:
        val = self._data.get("intervals_weight_kg")
        return float(val) if val is not None else None

    @intervals_weight_kg.setter
    def intervals_weight_kg(self, value: float | None) -> None:
        if value is None:
            self._data.pop("intervals_weight_kg", None)
        else:
            self._data["intervals_weight_kg"] = value
        self._save()

    @property
    def ftp(self) -> int | None:
        val = self._data.get("ftp")
        return int(val) if val is not None else None

    @ftp.setter
    def ftp(self, value: int | None) -> None:
        if value is None:
            self._data.pop("ftp", None)
        else:
            self._data["ftp"] = value
        self._save()

    @property
    def manual_ftp(self) -> int | None:
        val = self._data.get("manual_ftp")
        return int(val) if val is not None else None

    @manual_ftp.setter
    def manual_ftp(self, value: int | None) -> None:
        if value is None:
            self._data.pop("manual_ftp", None)
        else:
            self._data["manual_ftp"] = value
        self._save()

    @property
    def intervals_ftp(self) -> int | None:
        val = self._data.get("intervals_ftp")
        return int(val) if val is not None else None

    @intervals_ftp.setter
    def intervals_ftp(self, value: int | None) -> None:
        if value is None:
            self._data.pop("intervals_ftp", None)
        else:
            self._data["intervals_ftp"] = value
        self._save()

    @property
    def profile_source(self) -> str:
        val = self._data.get("profile_source", "manual")
        return val if val in {"manual", "intervals_icu"} else "manual"

    @profile_source.setter
    def profile_source(self, value: str) -> None:
        self._data["profile_source"] = value if value in {"manual", "intervals_icu"} else "manual"
        self._save()

    @property
    def intervals_api_key(self) -> str:
        raw = str(self._data.get("intervals_api_key", ""))
        return _decode_sensitive(raw)

    @intervals_api_key.setter
    def intervals_api_key(self, value: str | None) -> None:
        if value:
            self._data["intervals_api_key"] = _encode_sensitive(value)
        else:
            self._data.pop("intervals_api_key", None)
        self._save()

    @property
    def intervals_athlete_id(self) -> str:
        return str(self._data.get("intervals_athlete_id", ""))

    @intervals_athlete_id.setter
    def intervals_athlete_id(self, value: str | None) -> None:
        if value:
            self._data["intervals_athlete_id"] = value
        else:
            self._data.pop("intervals_athlete_id", None)
        self._save()

    @property
    def last_zwo_folder(self) -> str:
        return str(self._data.get("last_zwo_folder", ""))

    @last_zwo_folder.setter
    def last_zwo_folder(self, value: str | None) -> None:
        if value:
            self._data["last_zwo_folder"] = value
        else:
            self._data.pop("last_zwo_folder", None)
        self._save()

    @property
    def overlay_position(self) -> tuple[int, int] | None:
        pos = self._data.get("overlay_position")
        if pos and isinstance(pos, list) and len(pos) == 2:
            return (int(pos[0]), int(pos[1]))
        return None

    @overlay_position.setter
    def overlay_position(self, value: tuple[int, int] | None) -> None:
        if value is None:
            self._data.pop("overlay_position", None)
        else:
            self._data["overlay_position"] = list(value)
        self._save()

    @property
    def sensor_addresses(self) -> dict:
        value = self._data.get("sensor_addresses", {})
        if not isinstance(value, dict):
            return {}
        return {
            service: sensor
            for service, sensor in value.items()
            if isinstance(sensor, str) or (isinstance(sensor, dict) and sensor.get("address"))
        }

    @sensor_addresses.setter
    def sensor_addresses(self, value: dict) -> None:
        self._data["sensor_addresses"] = value if isinstance(value, dict) else {}
        self._save()

    @property
    def known_ble_devices(self) -> dict:
        value = self._data.get("known_ble_devices", {})
        if not isinstance(value, dict):
            return {}
        return {
            str(address): device
            for address, device in value.items()
            if isinstance(device, dict) and device.get("address")
        }

    @known_ble_devices.setter
    def known_ble_devices(self, value: dict) -> None:
        self._data["known_ble_devices"] = value if isinstance(value, dict) else {}
        self._save()

    @property
    def qz_ws_enabled(self) -> bool:
        return bool(self._data.get("qz_ws_enabled", False))

    @qz_ws_enabled.setter
    def qz_ws_enabled(self, value: bool) -> None:
        self._data["qz_ws_enabled"] = bool(value)
        self._save()

    @property
    def qz_ws_host(self) -> str:
        return str(self._data.get("qz_ws_host", "127.0.0.1"))

    @qz_ws_host.setter
    def qz_ws_host(self, value: str | None) -> None:
        self._data["qz_ws_host"] = str(value or "127.0.0.1")
        self._save()

    @property
    def qz_ws_port(self) -> int:
        try:
            return int(self._data.get("qz_ws_port", 34107))
        except (TypeError, ValueError):
            return 34107

    @qz_ws_port.setter
    def qz_ws_port(self, value: int | str | None) -> None:
        try:
            self._data["qz_ws_port"] = int(value) if value is not None else 34107
        except (TypeError, ValueError):
            self._data["qz_ws_port"] = 34107
        self._save()

    @property
    def qz_ws_auto_reconnect(self) -> bool:
        return bool(self._data.get("qz_ws_auto_reconnect", True))

    @qz_ws_auto_reconnect.setter
    def qz_ws_auto_reconnect(self, value: bool) -> None:
        self._data["qz_ws_auto_reconnect"] = bool(value)
        self._save()

    @property
    def qz_wifi_enabled(self) -> bool:
        return bool(self._data.get("qz_wifi_enabled", True))

    @qz_wifi_enabled.setter
    def qz_wifi_enabled(self, value: bool) -> None:
        self._data["qz_wifi_enabled"] = bool(value)
        self._save()

    @property
    def qz_dircon_host(self) -> str:
        return str(self._data.get("qz_dircon_host", ""))

    @qz_dircon_host.setter
    def qz_dircon_host(self, value: str | None) -> None:
        host = str(value or "").strip()
        if host:
            self._data["qz_dircon_host"] = host
        else:
            self._data.pop("qz_dircon_host", None)
        self._save()

    @property
    def qz_dircon_port(self) -> int:
        try:
            return int(self._data.get("qz_dircon_port", 36866))
        except (TypeError, ValueError):
            return 36866

    @qz_dircon_port.setter
    def qz_dircon_port(self, value: int | str | None) -> None:
        try:
            self._data["qz_dircon_port"] = int(value) if value is not None else 36866
        except (TypeError, ValueError):
            self._data["qz_dircon_port"] = 36866
        self._save()

    @property
    def qz_mqtt_enabled(self) -> bool:
        return bool(self._data.get("qz_mqtt_enabled", False))

    @qz_mqtt_enabled.setter
    def qz_mqtt_enabled(self, value: bool) -> None:
        self._data["qz_mqtt_enabled"] = bool(value)
        self._save()

    @property
    def qz_mqtt_host(self) -> str:
        return str(self._data.get("qz_mqtt_host", "127.0.0.1"))

    @qz_mqtt_host.setter
    def qz_mqtt_host(self, value: str | None) -> None:
        self._data["qz_mqtt_host"] = str(value or "127.0.0.1")
        self._save()

    @property
    def qz_mqtt_port(self) -> int:
        try:
            return int(self._data.get("qz_mqtt_port", 1883))
        except (TypeError, ValueError):
            return 1883

    @qz_mqtt_port.setter
    def qz_mqtt_port(self, value: int | str | None) -> None:
        try:
            self._data["qz_mqtt_port"] = int(value) if value is not None else 1883
        except (TypeError, ValueError):
            self._data["qz_mqtt_port"] = 1883
        self._save()

    @property
    def qz_mqtt_device(self) -> str:
        return str(self._data.get("qz_mqtt_device", "+"))

    @qz_mqtt_device.setter
    def qz_mqtt_device(self, value: str | None) -> None:
        self._data["qz_mqtt_device"] = str(value or "+")
        self._save()

    @property
    def qz_mqtt_username(self) -> str:
        return str(self._data.get("qz_mqtt_username", ""))

    @qz_mqtt_username.setter
    def qz_mqtt_username(self, value: str | None) -> None:
        if value:
            self._data["qz_mqtt_username"] = value
        else:
            self._data.pop("qz_mqtt_username", None)
        self._save()

    @property
    def qz_mqtt_password(self) -> str:
        raw = str(self._data.get("qz_mqtt_password", ""))
        return _decode_sensitive(raw)

    @qz_mqtt_password.setter
    def qz_mqtt_password(self, value: str | None) -> None:
        if value:
            self._data["qz_mqtt_password"] = _encode_sensitive(value)
        else:
            self._data.pop("qz_mqtt_password", None)
        self._save()
