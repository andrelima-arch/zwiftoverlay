import customtkinter as ctk

from app.core.events import Signal
from app.ui.i18n import normalize_language, t

NETWORK_SERVICE_LABELS = {
    "qz_dircon": "QZ Wi-Fi / Wahoo DIRCON",
}


class SensorSelector(ctk.CTkFrame):
    def __init__(self, parent=None, scan_parent=None, assigned_parent=None, language: str = "en", **kwargs):
        super().__init__(parent, **kwargs)
        self._language = normalize_language(language)
        self._hr_address: str | None = None
        self._power_address: str | None = None
        self._csc_address: str | None = None
        self._ftms_address: str | None = None
        self._selected_sensor_details: dict[str, dict[str, str]] = {}

        self.scan_button_clicked = Signal()
        self.device_connect_requested = Signal(str, str, dict)
        self.device_disconnect_requested = Signal(str)

        scan_container = scan_parent or self
        scan_frame = ctk.CTkFrame(scan_container)
        scan_frame.pack(fill="x", padx=5, pady=(5, 2))
        scan_frame.grid_columnconfigure(0, weight=1)
        self._scan_button = ctk.CTkButton(
            scan_frame, text=self._text("sensor.scan"),
            fg_color="#336699", command=self._on_scan,
        )
        self._scan_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self._scan_buttons = (self._scan_button,)

        self._status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._status_label.pack(fill="x", padx=5, pady=2)

        lists_frame = ctk.CTkFrame(self)
        lists_frame.pack(fill="both", expand=True, padx=5, pady=2)
        lists_frame.grid_columnconfigure((0, 1), weight=1)
        lists_frame.grid_rowconfigure(1, weight=1)

        self._connected_title_label = ctk.CTkLabel(lists_frame, text=self._text("sensor.connected"), font=ctk.CTkFont(weight="bold"))
        self._connected_title_label.grid(
            row=0, column=0, padx=3, pady=(2, 0), sticky="w"
        )
        self._available_title_label = ctk.CTkLabel(lists_frame, text=self._text("sensor.available"), font=ctk.CTkFont(weight="bold"))
        self._available_title_label.grid(
            row=0, column=1, padx=3, pady=(2, 0), sticky="w"
        )
        self._connected_list = ctk.CTkScrollableFrame(lists_frame, height=120)
        self._connected_list.grid(row=1, column=0, sticky="nsew", padx=(0, 3), pady=2)
        self._available_list = ctk.CTkScrollableFrame(lists_frame, height=120)
        self._available_list.grid(row=1, column=1, sticky="nsew", padx=(3, 0), pady=2)

        self._hint_label = ctk.CTkLabel(
            self,
            text=self._text("sensor.hint"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._hint_label.pack(fill="x", padx=5, pady=2)

        assigned_container = assigned_parent or self
        assigned_frame = ctk.CTkFrame(assigned_container)
        assigned_frame.pack(fill="x", padx=5, pady=5)

        self._selected_title_label = ctk.CTkLabel(assigned_frame, text=self._text("sensor.selected"), font=ctk.CTkFont(weight="bold"))
        self._selected_title_label.pack(anchor="w", padx=5)
        self._hr_label = ctk.CTkLabel(assigned_frame, text=f"HR: {self._text('sensor.none')}")
        self._hr_label.pack(anchor="w", padx=10)
        self._power_label = ctk.CTkLabel(assigned_frame, text=f"{self._text('sensor.power')}: {self._text('sensor.none')}")
        self._power_label.pack(anchor="w", padx=10)
        self._csc_label = ctk.CTkLabel(assigned_frame, text=f"{self._text('sensor.cadence')}: {self._text('sensor.none')}")
        self._csc_label.pack(anchor="w", padx=10)
        self._ftms_label = ctk.CTkLabel(assigned_frame, text=f"{self._text('sensor.smart_trainer')}: {self._text('sensor.none')}")
        self._ftms_label.pack(anchor="w", padx=10)

        self._scanned_devices: dict = {}
        self._device_buttons: dict = {}
        self._known_devices: dict[str, dict[str, str]] = {}
        self._connection_states: dict[str, str] = {}
        self._scan_generation = 0
        self._device_seen_generation: dict[str, int] = {}

    def set_language(self, language: str) -> None:
        self._language = normalize_language(language)
        self._scan_button.configure(text=self._text("sensor.scan"))
        self._connected_title_label.configure(text=self._text("sensor.connected"))
        self._available_title_label.configure(text=self._text("sensor.available"))
        self._hint_label.configure(text=self._text("sensor.hint"))
        self._selected_title_label.configure(text=self._text("sensor.selected"))
        self._refresh_assigned_labels()
        for device in list(self._scanned_devices.values()):
            self._render_device(device)

    def _text(self, key: str, **params) -> str:
        return t(getattr(self, "_language", "en"), key, **params)

    def set_known_devices(self, devices: dict) -> None:
        self._known_devices = {
            str(address): dict(details)
            for address, details in (devices or {}).items()
            if isinstance(details, dict)
        }

    def start_scan(self) -> None:
        self._scan_generation += 1

    def add_device(self, device) -> None:
        self._store_device(device, mark_seen=True)
        self._render_device(device)

    def set_scanning(self, scanning: bool) -> None:
        if scanning:
            self.start_scan()
        for button in self._scan_buttons:
            button.configure(state="disabled" if scanning else "normal")
        self._status_label.configure(text=self._text("sensor.searching") if scanning else "", text_color="gray")

    def set_status(self, text: str, text_color: str = "gray") -> None:
        self._status_label.configure(text=text, text_color=text_color)

    def scan_complete(self) -> None:
        current_seen = {
            address
            for address, generation in self._device_seen_generation.items()
            if generation == self._scan_generation
        }
        for address, device in list(self._scanned_devices.items()):
            if address in current_seen:
                continue
            if self._status_category(self._connection_states.get(address, "")) in {"connected", "connecting", "queued"}:
                continue
            self._connection_states[address] = "Stale"
            self._store_device(device, mark_seen=False)
            self._render_device(device)
        self._status_label.configure(text=self._text("sensor.found", count=len(current_seen)))
        for button in self._scan_buttons:
            button.configure(state="normal")

    def update_connection_status(self, address: str, status: str) -> None:
        color = "red" if status.startswith("Error") else "gray"
        self._status_label.configure(text=f"{address[:17]}... {status}", text_color=color)
        self._connection_states[address] = status
        device = self._scanned_devices.get(address)
        if device:
            self._render_device(device)
            return
        if self._status_category(status) not in {"connected", "connecting", "queued"}:
            button = self._device_buttons.pop(address, None)
            if button:
                button.destroy()

    def get_selected_sensors(self) -> dict[str, dict[str, str]]:
        result = {}
        for service, address in (
            ("hr", self._hr_address),
            ("power", self._power_address),
            ("csc", self._csc_address),
            ("ftms", self._ftms_address),
        ):
            if address:
                result[service] = self._sensor_details(service, address)
        return result

    def set_selected_sensors(self, sensors: dict[str, str | dict[str, str]]) -> None:
        self._selected_sensor_details = {}
        self._hr_address = self._address_from_config(sensors.get("hr"))
        self._power_address = self._address_from_config(sensors.get("power"))
        self._csc_address = self._address_from_config(sensors.get("csc"))
        self._ftms_address = self._address_from_config(sensors.get("ftms"))
        for service, value in sensors.items():
            if isinstance(value, dict) and value.get("address"):
                self._selected_sensor_details[service] = {
                    "address": str(value.get("address", "")),
                    "name": str(value.get("name", "")),
                    "service_type": str(value.get("service_type", service)),
                    "compatibility_hint": str(value.get("compatibility_hint", "")),
                    "compatibility_profile": str(value.get("compatibility_profile", "")),
                }
        self._refresh_assigned_labels()

    def _on_device_click(self, address: str) -> None:
        status = self._connection_states.get(address, "")
        category = self._status_category(status)
        if category == "connected":
            self.device_disconnect_requested.emit(address)
            return
        if category in {"connecting", "queued"}:
            return

        device = self._scanned_devices.get(address)
        if not device:
            return
        service = device.service_type or device.detect_service_type()
        if service == "unknown":
            self._status_label.configure(text=self._text("sensor.unknown_type"), text_color="red")
            return

        if service == "qz_dircon":
            details = self._device_to_details(device, service)
            self.device_connect_requested.emit(address, service, details)
            return

        if service == "hr":
            self._hr_address = address
        elif service == "power":
            self._power_address = address
        elif service == "csc":
            self._csc_address = address
        elif service == "ftms":
            self._ftms_address = address
        else:
            self._status_label.configure(text=self._text("sensor.unsupported_type"), text_color="red")
            return

        details = self._device_to_details(device, service)
        self._selected_sensor_details[service] = details
        self._refresh_assigned_labels()
        self.device_connect_requested.emit(address, service, details)

    def _on_scan(self) -> None:
        self.scan_button_clicked.emit()

    def _refresh_assigned_labels(self) -> None:
        self._hr_label.configure(text=f"HR: {self._label_for_address(self._hr_address)}")
        self._power_label.configure(text=f"{self._text('sensor.power')}: {self._label_for_address(self._power_address)}")
        self._csc_label.configure(text=f"{self._text('sensor.cadence')}: {self._label_for_address(self._csc_address)}")
        self._ftms_label.configure(text=f"{self._text('sensor.smart_trainer')}: {self._label_for_address(self._ftms_address)}")

    def _label_for_address(self, address: str | None) -> str:
        if not address:
            return self._text("sensor.none")
        device = self._scanned_devices.get(address)
        if device:
            label = device.display_name
            if device.compatibility_hint:
                label = f"{label} [{device.compatibility_hint}]"
            return label
        for details in self._selected_sensor_details.values():
            if details.get("address") == address:
                name = details.get("name") or address
                hint = details.get("compatibility_hint")
                return f"{name} ({address}) [{hint}]" if hint else f"{name} ({address})"
        return address

    def _address_from_config(self, value) -> str | None:
        if isinstance(value, dict):
            address = value.get("address")
            return str(address) if address else None
        return str(value) if value else None

    def _device_to_details(self, device, service: str) -> dict[str, str]:
        return {
            "address": device.address,
            "name": device.name or "",
            "service_type": service,
            "compatibility_hint": device.compatibility_hint or "",
            "compatibility_profile": device.compatibility_profile or "",
            "host": str(getattr(device, "host", "") or ""),
            "port": str(getattr(device, "port", "") or ""),
            "serial_number": str(getattr(device, "serial_number", "") or ""),
            "mac_address": str(getattr(device, "mac_address", "") or ""),
            "source_type": str(getattr(device, "source_type", "") or ""),
            "source_id": str(getattr(device, "address", "") or ""),
            "services": list(getattr(device, "services", []) or []),
        }

    def _sensor_details(self, service: str, address: str) -> dict[str, str]:
        device = self._scanned_devices.get(address)
        if device:
            return self._device_to_details(device, service)
        details = dict(self._selected_sensor_details.get(service, {}))
        if details:
            details["address"] = address
            details["service_type"] = details.get("service_type") or service
            return details
        return {
            "address": address,
            "name": "",
            "service_type": service,
            "compatibility_hint": "",
            "compatibility_profile": "",
        }

    def scanned_devices(self) -> dict:
        return dict(self._scanned_devices)

    def _refresh_device_colors(self) -> None:
        for address, button in self._device_buttons.items():
            device = self._scanned_devices.get(address)
            if not device:
                continue
            known = address in self._known_devices or self._matches_known_identity(device)
            saved = self._is_saved_device(device)
            button.configure(fg_color=self._button_color(address, known, saved, device.service_type))

    def _store_device(self, device, mark_seen: bool) -> None:
        self._scanned_devices[device.address] = device
        if mark_seen:
            self._device_seen_generation[device.address] = self._scan_generation

    def _render_device(self, device) -> None:
        from app.sensors.scanner import SERVICE_LABELS
        service_label = NETWORK_SERVICE_LABELS.get(
            device.service_type,
            SERVICE_LABELS.get(device.service_type, device.service_type),
        )
        details = self._known_devices.get(device.address)
        saved = self._is_saved_device(device)
        known = details is not None or self._matches_known_identity(device)
        if device.compatibility_hint:
            service_label = f"{service_label} / {device.compatibility_hint}"
        known_label = self._text("sensor.saved") if saved else self._text("sensor.recent") if known else self._text("sensor.new")
        display = f"{device.display_name} [{service_label}] [{known_label}]"
        self._render_device_button(device.address, display, known, saved, device.service_type)

    def _button_color(self, address: str, known: bool, saved: bool, service_type: str) -> str:
        status = self._connection_states.get(address, "")
        category = self._status_category(status)
        if category == "connected":
            return "#1f7a45"
        if category == "error":
            return "#8a3a3a"
        if category == "connecting":
            return "#7a6230"
        if category == "queued":
            return "#6a5f3b"
        if category == "stale":
            return "#3d3d3d"
        if service_type == "unknown":
            return "#5a4a4a"
        if saved:
            return "#2f6f4e"
        if known:
            return "#4a5f6a"
        return "#4a4a4a"

    def _render_device_button(self, address: str, display: str, known: bool, saved: bool, service_type: str) -> None:
        status = self._connection_states.get(address, "")
        if status:
            display = f"{display} - {status}"
        parent = self._connected_list if self._status_category(status) == "connected" else self._available_list
        old_button = self._device_buttons.pop(address, None)
        if old_button:
            old_button.destroy()
        button = ctk.CTkButton(
            parent,
            text=display,
            fg_color=self._button_color(address, known, saved, service_type),
            command=lambda addr=address: self._on_device_click(addr),
        )
        button.pack(fill="x", padx=2, pady=1)
        self._device_buttons[address] = button

    def _clear_device_buttons(self) -> None:
        for button in self._device_buttons.values():
            button.destroy()
        self._device_buttons = {}

    def _clear_available_device_buttons(self) -> None:
        for address, button in list(self._device_buttons.items()):
            if self._status_category(self._connection_states.get(address, "")) == "connected":
                continue
            button.destroy()
            self._device_buttons.pop(address, None)

    def _status_category(self, status: str) -> str:
        if status.startswith("Connected"):
            return "connected"
        if status.startswith("Connecting"):
            return "connecting"
        if status.startswith("Queued"):
            return "queued"
        if status.startswith("Error"):
            return "error"
        if status == "Disconnected":
            return "disconnected"
        if status == "Stale":
            return "stale"
        return ""

    def _matches_known_identity(self, device) -> bool:
        device_name = self._normalise_name(device.name)
        if not device_name:
            return False
        service = device.service_type or device.detect_service_type()
        profile = device.compatibility_profile or ""
        for details in self._known_devices.values():
            known_name = self._normalise_name(str(details.get("name", "")))
            known_service = str(details.get("service_type", ""))
            known_profile = str(details.get("compatibility_profile", ""))
            if known_name == device_name and (not known_service or known_service == service):
                if not known_profile or not profile or known_profile == profile:
                    return True
        return False

    def _is_saved_device(self, device) -> bool:
        if device.address in {
            address
            for address in (self._hr_address, self._power_address, self._csc_address, self._ftms_address)
            if address
        }:
            return True
        device_name = self._normalise_name(device.name)
        if not device_name:
            return False
        service = device.service_type or device.detect_service_type()
        profile = device.compatibility_profile or ""
        for details in self._selected_sensor_details.values():
            saved_name = self._normalise_name(str(details.get("name", "")))
            saved_service = str(details.get("service_type", ""))
            saved_profile = str(details.get("compatibility_profile", ""))
            if saved_name == device_name and (not saved_service or saved_service == service):
                if not saved_profile or not profile or saved_profile == profile:
                    return True
        return False

    def _normalise_name(self, name: str) -> str:
        return " ".join((name or "").upper().replace("_", " ").split())
