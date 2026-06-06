import customtkinter as ctk
from datetime import datetime, timezone

from app.core.events import Signal
from app.sensors.scanner import ScannedDevice
from app.sensors.reader import SensorReader
from app.models.workout import Workout, WorkoutInterval
from app.ui.i18n import normalize_language, t, toggle_language
from app.ui.workout_loader import WorkoutLoader
from app.ui.sensor_selector import SensorSelector

SCAN_WATCHDOG_MS = 15000


class MainWindow(ctk.CTk):
    def __init__(self, config, sensor_reader: SensorReader) -> None:
        super().__init__()
        self._config = config
        self._sensor_reader = sensor_reader
        self._ui_language = normalize_language(getattr(config, "ui_language", "en"))
        self._selected_workout: Workout = self._hardcoded_workout()
        self.profile_changed = Signal(float, int)
        self.language_changed = Signal(str)
        self.title(self._text("app.title"))
        self.geometry("700x500")
        self.resizable(False, False)

        self._active_profile_source = config.profile_source
        initial_weight, initial_ftp = self._get_profile_values(self._active_profile_source)
        self._weight_var = ctk.DoubleVar(value=float(initial_weight if initial_weight is not None else 75))
        self._ftp_var = ctk.IntVar(value=int(initial_ftp if initial_ftp is not None else 250))
        self._profile_source_var = ctk.StringVar(
            value=self._choice_from_source_key(config.profile_source)
        )

        # Compact header: title + language toggle
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(5, 0))
        header_frame.grid_columnconfigure(0, weight=1)

        self._language_button = ctk.CTkButton(
            header_frame,
            text=self._text("language.toggle"),
            width=56,
            command=self._toggle_ui_language,
        )
        self._language_button.grid(row=0, column=0, padx=0, pady=2, sticky="e")

        # Tabs
        self._tabview = ctk.CTkTabview(self)
        self._tabview.pack(fill="both", expand=True, padx=10, pady=(0, 0))

        self._profile_tab_name = self._text("tab.profile")
        self._workout_tab_name = self._text("tab.workout")
        self._sensor_tab_name = self._text("tab.sensors")
        self._qz_tab_name = self._text("tab.qz")
        self._profile_tab = self._tabview.add(self._profile_tab_name)
        self._workout_tab = self._tabview.add(self._workout_tab_name)
        self._sensor_tab = self._tabview.add(self._sensor_tab_name)
        self._qz_tab = self._tabview.add(self._qz_tab_name)

        # --- Profile Tab ---
        self._build_profile_tab()

        # --- Workout Tab ---
        self._workout_loader = WorkoutLoader(ftp=self.ftp, parent=self._workout_tab, config=self._config, language=self._ui_language)
        self._workout_loader.pack(fill="both", expand=True, padx=3, pady=3)
        self._workout_loader.workout_loaded.connect(self._on_workout_loaded)
        self._workout_loader.profile_synced.connect(self._on_intervals_profile_synced)
        self._workout_loader.profile_sync_failed.connect(self._on_intervals_profile_sync_failed)

        # --- Sensors Tab ---
        self._sensor_selector = SensorSelector(
            parent=self._sensor_tab,
            language=self._ui_language,
        )
        self._sensor_selector.pack(fill="both", expand=True, padx=3, pady=3)
        self._sensor_selector.scan_button_clicked.connect(self._on_scan)
        self._sensor_selector.device_connect_requested.connect(self._on_connect_device_requested)
        self._sensor_selector.device_disconnect_requested.connect(self._on_disconnect_device_requested)
        self._sensor_selector.set_known_devices(self._config.known_ble_devices)
        self._sensor_selector.set_selected_sensors(self._config.sensor_addresses)
        self._scan_seen_devices: dict[str, ScannedDevice] = {}
        self._scan_auto_connect = False
        self._scan_pending_sources: set[str] = set()
        self._scan_active = False
        self._scan_timeout_after_id = None

        # --- QZ Tab ---
        if not config.qz_wifi_enabled:
            config.qz_wifi_enabled = True
        self._qz_enabled_var = ctk.BooleanVar(value=True)
        self._qz_mqtt_enabled_var = ctk.BooleanVar(value=bool(config.qz_mqtt_enabled))
        self._qz_mqtt_host_var = ctk.StringVar(value=config.qz_mqtt_host)
        self._qz_mqtt_port_var = ctk.StringVar(value=str(config.qz_mqtt_port))
        self._qz_mqtt_device_var = ctk.StringVar(value=config.qz_mqtt_device)
        self._qz_mqtt_username_var = ctk.StringVar(value=config.qz_mqtt_username)
        self._qz_mqtt_password_var = ctk.StringVar(value=config.qz_mqtt_password)
        self._qz_dircon_host_var = ctk.StringVar(value=config.qz_dircon_host)
        self._qz_dircon_port_var = ctk.StringVar(value=str(config.qz_dircon_port))
        self._build_qz_tab()

        # --- Bottom action bar ---
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.pack(fill="x", padx=10, pady=(0, 5))
        bottom_frame.grid_columnconfigure(2, weight=1)

        self._start_button = ctk.CTkButton(
            bottom_frame, text=self._text("workout.start"),
            fg_color="#336699", font=ctk.CTkFont(size=13, weight="bold"),
            width=100,
        )
        self._start_button.grid(row=0, column=0, padx=(5, 3), pady=5, sticky="w")

        self._stop_button = ctk.CTkButton(
            bottom_frame, text=self._text("workout.stop"),
            fg_color="#cc3333", font=ctk.CTkFont(size=13, weight="bold"),
            width=100,
        )
        self._stop_button.grid(row=0, column=1, padx=(3, 5), pady=5, sticky="w")
        self._stop_button.configure(state="disabled")

        self._workout_info = ctk.CTkLabel(
            bottom_frame,
            text=self._format_workout_info(self._selected_workout, "workout.imported"),
            font=ctk.CTkFont(size=11),
            wraplength=350,
        )
        self._workout_info.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        self._connect_sensor_signals()
        self._on_profile_source_changed(self._profile_source_var.get())
        self.after(800, self._sync_intervals_on_startup)
        if self._qz_enabled_var.get():
            self.after(1000, self._scan_qz_wifi)
        if self._qz_mqtt_enabled_var.get():
            self.after(1200, self._connect_qz_mqtt)
        if self._config.sensor_addresses:
            self.after(500, self._on_startup_scan)

    def _hardcoded_workout(self):
        return Workout(
            title=self._text("workout.test_title"),
            intervals=[
                WorkoutInterval(name="Warmup", duration_seconds=840, power_min=112, power_max=186, cadence_target=85, type="ramp"),
                WorkoutInterval(name="Endurance", duration_seconds=660, power_min=161, power_max=186, cadence_target=88, type="steady", repeat_total=6),
                WorkoutInterval(name="Sprint", duration_seconds=10, power_min=373, power_max=373, cadence_target=110, type="sprint", repeat_total=6),
                WorkoutInterval(name="Cooldown", duration_seconds=540, power_min=161, power_max=112, cadence_target=85, type="ramp"),
            ],
        )

    @property
    def start_button(self):
        return self._start_button

    @property
    def stop_button(self):
        return self._stop_button

    @property
    def weight_kg(self) -> float:
        return self._weight_var.get()

    @property
    def ftp(self) -> int:
        return self._ftp_var.get()

    @property
    def selected_workout(self):
        return self._selected_workout

    @property
    def sensor_selector(self):
        return self._sensor_selector

    def save_config(self) -> None:
        self._capture_current_profile_values(self.profile_source)
        self._config.ui_language = self._ui_language
        self._config.profile_source = self.profile_source
        self._config.weight_kg = self.weight_kg
        self._config.ftp = self.ftp
        self._workout_loader.set_ftp(self.ftp)
        self._save_intervals_credentials()
        self._config.sensor_addresses = self._sensor_selector.get_selected_sensors()
        self._config.known_ble_devices = self._merge_known_with_selected()
        self._save_qz_config()

    @property
    def profile_source(self) -> str:
        return self._source_key_from_choice(self._profile_source_var.get())

    def set_running(self, running: bool) -> None:
        if running:
            self._start_button.configure(state="disabled")
            self._stop_button.configure(state="normal")
        else:
            self._start_button.configure(state="normal")
            self._stop_button.configure(state="disabled")

    def _on_workout_loaded(self, workout) -> None:
        self._selected_workout = workout
        self._workout_info.configure(text=self._format_workout_info(workout, "workout.imported"))

    def _on_scan(self) -> None:
        self._start_sensor_scan(auto_connect=False)

    def _on_startup_scan(self) -> None:
        self._start_sensor_scan(auto_connect=True)

    def _start_sensor_scan(self, auto_connect: bool = False) -> None:
        if self._scan_active:
            self._sensor_selector.set_status(self._text("main.scan_in_progress"), "gray")
            return
        self._scan_active = True
        self._scan_auto_connect = auto_connect
        self._scan_seen_devices = {}
        self._scan_pending_sources = {"ble", "qz"}
        self._sensor_selector.set_known_devices(self._config.known_ble_devices)
        self._sensor_selector.set_scanning(True)
        self._schedule_scan_watchdog()
        self._sensor_reader.scan()
        self._scan_qz_wifi()

    def _on_connect_device_requested(self, address: str, service: str, details: dict) -> None:
        if not address or service == "unknown":
            return
        if service in {"qz_dircon", "qz_websocket"}:
            if isinstance(details, dict):
                known = self._config.known_ble_devices
                known = self._upsert_known_details(known, {
                    **known.get(address, {}),
                    **details,
                    "address": address,
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                })
                self._config.known_ble_devices = known
                self._sensor_selector.set_known_devices(known)
            self._sensor_reader.connect_network_device(address, service, details)
            return
        sensors = self._sensor_selector.get_selected_sensors()
        self._config.sensor_addresses = sensors
        if isinstance(details, dict):
            known = self._config.known_ble_devices
            known = self._upsert_known_details(known, {
                **known.get(address, {}),
                **details,
                "address": address,
                "last_seen": datetime.now(timezone.utc).isoformat(),
            })
            self._config.known_ble_devices = known
        self._config.known_ble_devices = self._merge_known_with_selected()
        self._sensor_selector.set_known_devices(self._config.known_ble_devices)
        self._sensor_reader.connect_device(address, service, details)

    def _on_disconnect_device_requested(self, address: str) -> None:
        if not address:
            return
        if address.startswith(("qz-dircon:", "qz-ws:")):
            self._sensor_reader.disconnect_network_device(address)
            return
        self._sensor_reader.disconnect_device(address)

    def _connect_sensor_signals(self) -> None:
        self._sensor_reader.scan_device_found.connect(self._on_device_found)
        self._sensor_reader.network_device_found.connect(self._on_network_device_found)
        self._sensor_reader.scan_complete.connect(self._on_scan_complete)
        self._sensor_reader.connection_status_changed.connect(self._on_connection_status)
        self._sensor_reader.qz_connection_status_changed.connect(self._on_qz_connection_status)

    def _on_device_found(self, device: ScannedDevice) -> None:
        self._scan_seen_devices[device.address] = device
        self._sensor_selector.add_device(device)
        self._remember_known_device(device)

    def _on_network_device_found(self, device) -> None:
        self._sensor_selector.add_device(device)
        known = self._config.known_ble_devices
        known = self._upsert_known_details(known, {
            "address": device.address,
            "name": device.name or "",
            "service_type": device.service_type,
            "compatibility_hint": device.compatibility_hint or "",
            "compatibility_profile": device.compatibility_profile or "",
            "host": str(getattr(device, "host", "") or ""),
            "port": str(getattr(device, "port", "") or ""),
            "serial_number": str(getattr(device, "serial_number", "") or ""),
            "mac_address": str(getattr(device, "mac_address", "") or ""),
            "source_type": str(getattr(device, "source_type", "") or ""),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        })
        self._config.known_ble_devices = known
        self._sensor_selector.set_known_devices(known)

    def _on_scan_complete(self) -> None:
        self._complete_scan_source("ble")

    def _on_connection_status(self, address: str, status: str) -> None:
        self._sensor_selector.update_connection_status(address, status)

    def _build_profile_tab(self) -> None:
        """Build the compact Profile tab with athlete settings and Intervals.icu credentials."""
        frame = ctk.CTkFrame(self._profile_tab, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=3, pady=3)
        frame.grid_columnconfigure(1, weight=1)

        row = 0
        self._athlete_section_label = ctk.CTkLabel(frame, text=self._text("profile.section"), font=ctk.CTkFont(weight="bold"))
        self._athlete_section_label.grid(row=row, column=0, columnspan=2, padx=5, pady=(5, 2), sticky="w")
        row += 1

        self._profile_source_label = ctk.CTkLabel(frame, text=self._text("profile.source"))
        self._profile_source_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
        self._profile_source_menu = ctk.CTkOptionMenu(
            frame,
            values=[self._choice_from_source_key("manual"), "Intervals.icu"],
            variable=self._profile_source_var,
            command=self._on_profile_source_changed,
        )
        self._profile_source_menu.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        self._weight_label = ctk.CTkLabel(frame, text=self._text("profile.weight"))
        self._weight_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
        self._weight_entry = ctk.CTkEntry(frame, textvariable=self._weight_var, width=80)
        self._weight_entry.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        self._weight_entry.bind("<FocusOut>", lambda _event: self._apply_manual_profile_from_entries())
        self._weight_entry.bind("<Return>", lambda _event: self._apply_manual_profile_from_entries())
        self._weight_value_label = ctk.CTkLabel(frame, text="", anchor="w")
        self._weight_value_label.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        self._weight_value_label.grid_remove()
        row += 1

        self._ftp_label = ctk.CTkLabel(frame, text=self._text("profile.ftp"))
        self._ftp_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")
        self._ftp_entry = ctk.CTkEntry(frame, textvariable=self._ftp_var, width=80)
        self._ftp_entry.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        self._ftp_entry.bind("<FocusOut>", lambda _event: self._apply_manual_profile_from_entries())
        self._ftp_entry.bind("<Return>", lambda _event: self._apply_manual_profile_from_entries())
        self._ftp_value_label = ctk.CTkLabel(frame, text="", anchor="w")
        self._ftp_value_label.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        self._ftp_value_label.grid_remove()
        row += 1

        # Intervals.icu credentials
        self._intervals_frame = ctk.CTkFrame(frame)
        self._intervals_frame.grid(row=row, column=0, columnspan=2, padx=5, pady=(5, 2), sticky="ew")
        self._intervals_frame.grid_columnconfigure(1, weight=1)
        row += 1

        self._intervals_api_key_label = ctk.CTkLabel(self._intervals_frame, text="Intervals API Key:")
        self._intervals_api_key_label.grid(row=0, column=0, padx=5, pady=3, sticky="w")
        self._intervals_api_key_entry = ctk.CTkEntry(self._intervals_frame, show="*")
        self._intervals_api_key_entry.grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        self._intervals_api_key_entry.insert(0, self._config.intervals_api_key)

        self._intervals_athlete_id_label = ctk.CTkLabel(self._intervals_frame, text="Athlete ID:")
        self._intervals_athlete_id_label.grid(row=1, column=0, padx=5, pady=3, sticky="w")
        self._intervals_athlete_id_entry = ctk.CTkEntry(self._intervals_frame)
        self._intervals_athlete_id_entry.grid(row=1, column=1, padx=5, pady=3, sticky="ew")
        self._intervals_athlete_id_entry.insert(0, self._config.intervals_athlete_id)

        self._save_intervals_button = ctk.CTkButton(
            self._intervals_frame,
            text=self._text("profile.save_intervals"),
            width=120,
            command=self._save_and_sync_intervals_credentials,
        )
        self._save_intervals_button.grid(row=2, column=0, columnspan=2, padx=5, pady=(0, 3), sticky="ew")

        self._profile_sync_status_label = ctk.CTkLabel(
            self._intervals_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=350,
        )
        self._profile_sync_status_label.grid(row=3, column=0, columnspan=2, padx=5, pady=(0, 3), sticky="w")

    def _build_qz_tab(self) -> None:
        self._qz_status_text = self._text("qz.disconnected")
        self._qz_status_label = ctk.CTkLabel(self._qz_tab, text="")

    def _on_qz_enabled_changed(self) -> None:
        self._save_qz_config()
        if self._qz_enabled_var.get():
            self._scan_qz_wifi()
        else:
            self._disconnect_qz_wifi()

    def _on_qz_mqtt_enabled_changed(self) -> None:
        self._save_qz_config()
        if self._qz_mqtt_enabled_var.get():
            self._connect_qz_mqtt()
        else:
            self._disconnect_qz_mqtt()

    def _scan_qz_wifi(self) -> None:
        self._save_qz_config()
        try:
            self._sensor_reader.scan_qz_wifi()
        except Exception as exc:
            self._on_qz_connection_status(f"QZ Wi-Fi erro: {exc}")

    def _disconnect_qz_wifi(self) -> None:
        self._sensor_reader.disconnect_qz_wifi()

    def _connect_qz_dircon_manual(self) -> None:
        self._save_qz_config()
        host = self._qz_dircon_host_var.get().strip()
        if not host:
            self._on_qz_connection_status(self._text("qz.host_required"))
            return
        self._sensor_reader.connect_qz_dircon_manual(host, self._qz_dircon_port_var.get())

    def _connect_qz_mqtt(self) -> None:
        self._save_qz_config()
        try:
            port = int(self._qz_mqtt_port_var.get() or "1883")
        except ValueError:
            port = 1883
            self._qz_mqtt_port_var.set("1883")
        self._sensor_reader.connect_qz_mqtt(
            self._qz_mqtt_host_var.get(),
            port,
            self._qz_mqtt_username_var.get(),
            self._qz_mqtt_password_var.get(),
            self._qz_mqtt_device_var.get() or "+",
        )

    def _disconnect_qz_mqtt(self) -> None:
        self._sensor_reader.disconnect_qz_mqtt()

    def _on_qz_connection_status(self, status: str) -> None:
        self._qz_status_text = status
        color = "red" if status.startswith("Error") else "gray"
        if status.startswith("Connected"):
            color = "green"
        self._qz_status_label.configure(text=self._text("qz.sources", status=status), text_color=color)
        terminal_scan_statuses = (
            "QZ DIRCON encontrado",
            "QZ Android encontrado",
            "QZ Wi-Fi encontrado",
            "mDNS não encontrou QZ",
            "QZ Wi-Fi indisponível",
            "QZ Wi-Fi erro",
            "QZ Wi-Fi ocupado",
            "No compatible QZ/Wi-Fi device found",
        )
        if status.startswith(terminal_scan_statuses):
            self._complete_scan_source("qz")

    def _complete_scan_source(self, source: str) -> None:
        if not self._scan_pending_sources:
            return
        self._scan_pending_sources.discard(source)
        if self._scan_pending_sources:
            return
        self._cancel_scan_watchdog()
        self._scan_active = False
        self._sensor_selector.scan_complete()
        self._config.known_ble_devices = self._merge_known_with_selected()
        if self._scan_auto_connect:
            self._auto_connect_saved_devices()
        self._scan_auto_connect = False

    def _schedule_scan_watchdog(self) -> None:
        self._cancel_scan_watchdog()
        self._scan_timeout_after_id = self.after(SCAN_WATCHDOG_MS, self._on_scan_watchdog_timeout)

    def _cancel_scan_watchdog(self) -> None:
        if not self._scan_timeout_after_id:
            return
        try:
            self.after_cancel(self._scan_timeout_after_id)
        except Exception:
            pass
        self._scan_timeout_after_id = None

    def _on_scan_watchdog_timeout(self) -> None:
        self._scan_timeout_after_id = None
        if not self._scan_pending_sources:
            return
        pending = ", ".join(sorted(self._scan_pending_sources))
        self._scan_pending_sources.clear()
        self._scan_active = False
        self._sensor_selector.scan_complete()
        self._sensor_selector.set_status(self._text("main.scan_timeout", pending=pending), "gray")
        self._config.known_ble_devices = self._merge_known_with_selected()
        if self._scan_auto_connect:
            self._auto_connect_saved_devices()
        self._scan_auto_connect = False

    def _save_qz_config(self) -> None:
        self._qz_enabled_var.set(True)
        self._config.qz_wifi_enabled = True
        self._config.qz_mqtt_enabled = self._qz_mqtt_enabled_var.get()
        self._config.qz_mqtt_host = self._qz_mqtt_host_var.get()
        self._config.qz_mqtt_port = self._qz_mqtt_port_var.get()
        self._config.qz_mqtt_device = self._qz_mqtt_device_var.get() or "+"
        self._config.qz_mqtt_username = self._qz_mqtt_username_var.get()
        self._config.qz_mqtt_password = self._qz_mqtt_password_var.get()
        self._config.qz_dircon_host = self._qz_dircon_host_var.get().strip()
        self._config.qz_dircon_port = self._qz_dircon_port_var.get()

    def _auto_connect_saved_devices(self) -> None:
        saved = self._config.sensor_addresses
        updated = dict(saved)
        changed = False

        for saved_service, sensor in saved.items():
            saved_details = sensor if isinstance(sensor, dict) else {"address": sensor, "service_type": saved_service}
            matched = self._match_saved_device(saved_details)
            if not matched:
                continue
            service = matched.service_type or matched.detect_service_type()
            if service == "unknown":
                continue
            details = self._device_to_sensor_details(matched, service)
            if saved_service != service:
                updated.pop(saved_service, None)
                changed = True
            if updated.get(service) != details:
                updated[service] = details
                changed = True
            self._sensor_reader.connect_device(matched.address, service, details)

        if changed:
            self._config.sensor_addresses = updated
            self._sensor_selector.set_selected_sensors(updated)

    def _match_saved_device(self, saved_details: dict) -> ScannedDevice | None:
        saved_address = str(saved_details.get("address", ""))
        if saved_address in self._scan_seen_devices:
            return self._scan_seen_devices[saved_address]

        saved_name = self._normalise_device_name(str(saved_details.get("name", "")))
        saved_service = str(saved_details.get("service_type", ""))
        saved_profile = str(saved_details.get("compatibility_profile", ""))
        if not saved_name:
            return None

        for device in self._scan_seen_devices.values():
            device_name = self._normalise_device_name(device.name)
            device_service = device.service_type or device.detect_service_type()
            device_profile = device.compatibility_profile or ""
            if device_name != saved_name:
                continue
            if saved_service and device_service != saved_service:
                continue
            if saved_profile and device_profile and saved_profile != device_profile:
                continue
            return device
        return None

    def _remember_known_device(self, device: ScannedDevice) -> None:
        known = self._config.known_ble_devices
        known = self._upsert_known_details(known, self._device_to_known_details(device))
        self._config.known_ble_devices = known
        self._sensor_selector.set_known_devices(known)

    def _merge_known_with_selected(self) -> dict:
        known = self._config.known_ble_devices
        for sensor in self._sensor_selector.get_selected_sensors().values():
            if isinstance(sensor, dict) and sensor.get("address"):
                known = self._upsert_known_details(known, {
                    **known.get(str(sensor["address"]), {}),
                    **sensor,
                    "address": str(sensor["address"]),
                    "last_seen": known.get(str(sensor["address"]), {}).get("last_seen", ""),
                }, preserve_selected=True)
        return known

    def _device_to_sensor_details(self, device: ScannedDevice, service: str) -> dict[str, str]:
        return {
            "address": device.address,
            "name": device.name or "",
            "service_type": service,
            "compatibility_hint": device.compatibility_hint or "",
            "compatibility_profile": device.compatibility_profile or "",
        }

    def _device_to_known_details(self, device: ScannedDevice) -> dict[str, str]:
        service = device.service_type or device.detect_service_type()
        return {
            **self._device_to_sensor_details(device, service),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

    def _normalise_device_name(self, name: str) -> str:
        return " ".join((name or "").upper().replace("_", " ").split())

    def _upsert_known_details(
        self,
        known: dict,
        details: dict,
        *,
        preserve_selected: bool = False,
    ) -> dict:
        address = str(details.get("address", "") or "")
        if not address:
            return known
        updated = dict(known)
        selected_addresses = {
            str(sensor.get("address", ""))
            for sensor in self._sensor_selector.get_selected_sensors().values()
            if isinstance(sensor, dict) and sensor.get("address")
        } if preserve_selected else set()
        identity = self._known_device_identity(details)
        for existing_address, existing_details in list(updated.items()):
            if existing_address == address:
                continue
            if existing_address in selected_addresses:
                continue
            if self._known_device_identity(existing_details) == identity:
                updated.pop(existing_address, None)
        updated[address] = details
        return updated

    def _known_device_identity(self, details: dict) -> tuple[str, ...]:
        service = str(details.get("service_type", "") or "")
        host = str(details.get("host", "") or "")
        port = str(details.get("port", "") or "")
        if service in {"qz_dircon", "qz_websocket"}:
            return (service, host, port)
        name = self._normalise_device_name(str(details.get("name", "") or ""))
        profile = str(details.get("compatibility_profile", "") or "")
        if service and service != "unknown" and name:
            return (service, profile, name)
        return ("address", str(details.get("address", "") or ""))

    def _on_profile_source_changed(self, choice: str) -> None:
        source = self._source_key_from_choice(choice)
        self._apply_active_profile(source)
        if source == "intervals_icu":
            self._weight_entry.grid_remove()
            self._ftp_entry.grid_remove()
            self._weight_value_label.grid()
            self._ftp_value_label.grid()
        else:
            self._weight_value_label.grid_remove()
            self._ftp_value_label.grid_remove()
            self._weight_entry.grid()
            self._ftp_entry.grid()
            self._weight_entry.configure(state="normal")
            self._ftp_entry.configure(state="normal")
        self._refresh_profile_value_display()

    def _source_key_from_choice(self, choice: str) -> str:
        return "intervals_icu" if choice == "Intervals.icu" else "manual"

    def _choice_from_source_key(self, source: str) -> str:
        return "Intervals.icu" if source == "intervals_icu" else self._text("profile.manual")

    def _text(self, key: str, **params) -> str:
        return t(getattr(self, "_ui_language", "en"), key, **params)

    def _format_workout_info(self, workout, fallback_key: str) -> str:
        expanded = workout.expanded_intervals()
        return self._text(
            "workout.info",
            title=workout.title or self._text(fallback_key),
            count=len(expanded),
        )

    def _toggle_ui_language(self) -> None:
        self._ui_language = toggle_language(self._ui_language)
        self._config.ui_language = self._ui_language
        self._apply_language_texts()
        self.language_changed.emit(self._ui_language)

    def _apply_language_texts(self) -> None:
        try:
            self.title(self._text("app.title"))
        except Exception:
            pass
        current_source = self.profile_source
        text_updates = {
            "_language_button": self._text("language.toggle"),
            "_athlete_section_label": self._text("profile.section"),
            "_profile_source_label": self._text("profile.source"),
            "_weight_label": self._text("profile.weight"),
            "_ftp_label": self._text("profile.ftp"),
            "_save_intervals_button": self._text("profile.save_intervals"),
            "_workout_section_label": self._text("workout.section"),
            "_start_button": self._text("workout.start"),
            "_stop_button": self._text("workout.stop"),
            "_qz_mqtt_enabled_check": self._text("qz.mqtt_enabled"),
            "_qz_mqtt_port_label": self._text("qz.port"),
            "_qz_mqtt_username_label": self._text("qz.username"),
            "_qz_mqtt_password_label": self._text("qz.password"),
            "_qz_mqtt_connect_button": self._text("qz.connect_mqtt"),
            "_qz_mqtt_disconnect_button": self._text("qz.disconnect"),
            "_qz_enabled_check": self._text("qz.wifi_enabled"),
            "_qz_help_label": self._text("qz.help"),
            "_qz_dircon_port_label": self._text("qz.port"),
            "_qz_dircon_manual_button": self._text("qz.connect_dircon_manual"),
            "_qz_connect_button": self._text("qz.scan"),
            "_qz_disconnect_button": self._text("qz.disconnect_wifi"),
        }
        for attr, text in text_updates.items():
            widget = self.__dict__.get(attr)
            if widget is not None:
                widget.configure(text=text)
        if "_profile_source_menu" in self.__dict__:
            self._profile_source_menu.configure(values=[self._choice_from_source_key("manual"), "Intervals.icu"])
        if "_profile_source_var" in self.__dict__:
            self._profile_source_var.set(self._choice_from_source_key(current_source))
        if "_workout_info" in self.__dict__:
            self._workout_info.configure(text=self._format_workout_info(self._selected_workout, "workout.imported"))
        if "_qz_status_label" in self.__dict__:
            status = self.__dict__.get("_qz_status_text", self._text("qz.disconnected"))
            self._qz_status_label.configure(text=self._text("qz.sources", status=status))
        self._rename_tabs()
        if "_workout_loader" in self.__dict__:
            self._workout_loader.set_language(self._ui_language)
        if "_sensor_selector" in self.__dict__:
            self._sensor_selector.set_language(self._ui_language)

    def _rename_tabs(self) -> None:
        if "_tabview" not in self.__dict__:
            return
        new_names = {
            "_profile_tab_name": self._text("tab.profile"),
            "_workout_tab_name": self._text("tab.workout"),
            "_sensor_tab_name": self._text("tab.sensors"),
            "_qz_tab_name": self._text("tab.qz"),
        }
        for attr, new_name in new_names.items():
            old_name = getattr(self, attr, None)
            if old_name and old_name != new_name:
                self._tabview.rename(old_name, new_name)
                setattr(self, attr, new_name)

    def _get_profile_values(self, source: str) -> tuple[float | None, int | None]:
        if source == "intervals_icu":
            weight = getattr(self._config, "intervals_weight_kg", None)
            ftp = getattr(self._config, "intervals_ftp", None)
            if weight is None and getattr(self._config, "profile_source", "") == "intervals_icu":
                weight = getattr(self._config, "weight_kg", None)
            if ftp is None and getattr(self._config, "profile_source", "") == "intervals_icu":
                ftp = getattr(self._config, "ftp", None)
            return weight, ftp

        weight = getattr(self._config, "manual_weight_kg", None)
        ftp = getattr(self._config, "manual_ftp", None)
        if weight is None:
            weight = getattr(self._config, "weight_kg", None)
        if ftp is None:
            ftp = getattr(self._config, "ftp", None)
        return weight, ftp

    def _store_profile_values(self, source: str, weight: float | None, ftp: int | None) -> None:
        if source == "intervals_icu":
            if hasattr(self._config, "intervals_weight_kg"):
                self._config.intervals_weight_kg = weight
            if hasattr(self._config, "intervals_ftp"):
                self._config.intervals_ftp = ftp
        else:
            if hasattr(self._config, "manual_weight_kg"):
                self._config.manual_weight_kg = weight
            if hasattr(self._config, "manual_ftp"):
                self._config.manual_ftp = ftp

    def _capture_current_profile_values(self, source: str) -> None:
        self._store_profile_values(source, self._read_weight_var(), self._read_ftp_var())

    def _apply_manual_profile_from_entries(self) -> None:
        if self.profile_source == "manual":
            self._apply_active_profile("manual", capture_previous=False)

    def _apply_active_profile(
        self,
        source: str,
        *,
        capture_previous: bool = True,
        rebuild_workout: bool = True,
    ) -> None:
        previous_source = getattr(self, "_active_profile_source", None)
        if capture_previous and previous_source:
            self._capture_current_profile_values(previous_source)

        source = source if source in {"manual", "intervals_icu"} else "manual"
        weight, ftp = self._get_profile_values(source)
        if weight is None:
            weight = self._read_weight_var()
        if ftp is None:
            ftp = self._read_ftp_var()

        self._active_profile_source = source
        self._profile_source_var.set(self._choice_from_source_key(source))
        self._config.profile_source = source
        self._weight_var.set(float(weight) if weight is not None else 75.0)
        self._ftp_var.set(int(ftp) if ftp is not None else 250)
        self._config.weight_kg = self.weight_kg
        self._config.ftp = self.ftp
        self._workout_loader.set_ftp(self.ftp)

        if rebuild_workout and hasattr(self._workout_loader, "rebuild_current_workout_for_ftp"):
            rebuilt = self._workout_loader.rebuild_current_workout_for_ftp(self.ftp)
            if rebuilt:
                self._on_workout_loaded(rebuilt)

        self._refresh_profile_value_display()
        self.profile_changed.emit(self.weight_kg, self.ftp)

    def _read_weight_var(self) -> float | None:
        try:
            value = self._weight_var.get()
        except Exception:
            return None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _read_ftp_var(self) -> int | None:
        try:
            value = self._ftp_var.get()
        except Exception:
            return None
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _refresh_profile_value_display(self) -> None:
        if hasattr(self, "_weight_value_label"):
            self._weight_value_label.configure(text=self._format_weight_display())
        if hasattr(self, "_ftp_value_label"):
            self._ftp_value_label.configure(text=self._format_ftp_display())

    def _format_weight_display(self) -> str:
        try:
            weight = self.weight_kg
        except Exception:
            return "-- kg"
        if weight is None:
            return "-- kg"
        return f"{float(weight):g} kg"

    def _format_ftp_display(self) -> str:
        try:
            ftp = self.ftp
        except Exception:
            return "-- W"
        if ftp is None:
            return "-- W"
        return f"{int(ftp)} W"

    def _sync_intervals_on_startup(self) -> None:
        if self.profile_source != "intervals_icu":
            return
        self._save_intervals_credentials()
        if not self._config.intervals_api_key or not self._config.intervals_athlete_id:
            return
        self._set_profile_sync_status(self._text("profile.syncing"), "gray")
        self._workout_loader.fetch_intervals_workouts()

    def _save_intervals_credentials(self) -> None:
        api_key = self._intervals_api_key_entry.get().strip()
        athlete_id = self._intervals_athlete_id_entry.get().strip()
        self._config.intervals_api_key = api_key
        self._config.intervals_athlete_id = athlete_id
        self._workout_loader.set_intervals_credentials(api_key, athlete_id)

    def _save_and_sync_intervals_credentials(self) -> None:
        self._save_intervals_credentials()
        self._profile_source_var.set("Intervals.icu")
        self._apply_active_profile("intervals_icu")
        if not self._config.intervals_api_key or not self._config.intervals_athlete_id:
            self._set_profile_sync_status(self._text("profile.missing_credentials"), "red")
            return
        self._set_profile_sync_status(self._text("profile.syncing"), "gray")
        self._workout_loader.fetch_intervals_workouts()

    def _on_intervals_profile_synced(self, profile) -> None:
        details = []
        if profile.weight_kg is not None:
            self._config.intervals_weight_kg = profile.weight_kg
            details.append(f"{profile.weight_kg:g}kg")
        if profile.ftp is not None:
            self._config.intervals_ftp = profile.ftp
            details.append(f"{profile.ftp}w")
        self._apply_active_profile("intervals_icu", capture_previous=False)
        if details:
            self._set_profile_sync_status(self._text("profile.updated", details=", ".join(details)), "green")
        else:
            self._set_profile_sync_status(self._text("profile.no_metrics"), "orange")

    def _on_intervals_profile_sync_failed(self, message: str) -> None:
        self._set_profile_sync_status(message or self._text("profile.sync_failed"), "red")

    def _set_profile_sync_status(self, text: str, color: str = "gray") -> None:
        if hasattr(self, "_profile_sync_status_label"):
            self._profile_sync_status_label.configure(text=text, text_color=color)
