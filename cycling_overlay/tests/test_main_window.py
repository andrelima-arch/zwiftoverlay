from types import SimpleNamespace

from app.core.events import Signal
from app.ui.main_window import MainWindow


class _FakeSelector:
    def __init__(self):
        self.scanning = []
        self.statuses = []
        self.scan_complete_count = 0
        self.known_devices = {}
        self.devices = []

    def set_known_devices(self, devices):
        self.known_devices = devices

    def add_device(self, device):
        self.devices.append(device)

    def set_scanning(self, scanning):
        self.scanning.append(scanning)

    def scan_complete(self):
        self.scan_complete_count += 1

    def set_status(self, text, text_color="gray"):
        self.statuses.append((text, text_color))

    def get_selected_sensors(self):
        return {}

    def set_language(self, _language):
        pass


class _FakeReader:
    def __init__(self):
        self.scan_count = 0
        self.network_disconnects = []
        self.ble_disconnects = []

    def scan(self):
        self.scan_count += 1

    def disconnect_network_device(self, address):
        self.network_disconnects.append(address)

    def disconnect_device(self, address):
        self.ble_disconnects.append(address)


class _FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FakeEntry:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class _FakeWidget:
    def __init__(self):
        self.configures = []
        self.grid_count = 0
        self.grid_remove_count = 0

    def configure(self, **kwargs):
        self.configures.append(kwargs)

    def grid(self, **_kwargs):
        self.grid_count += 1

    def grid_remove(self):
        self.grid_remove_count += 1


class _FakeWorkoutLoader:
    def __init__(self):
        self.credentials = []
        self.fetch_count = 0
        self.ftp = None
        self.language = None

    def set_intervals_credentials(self, api_key, athlete_id):
        self.credentials.append((api_key, athlete_id))

    def fetch_intervals_workouts(self):
        self.fetch_count += 1

    def set_ftp(self, ftp):
        self.ftp = ftp

    def rebuild_current_workout_for_ftp(self, _ftp):
        return None

    def set_language(self, language):
        self.language = language


def _window_stub(monkeypatch):
    window = object.__new__(MainWindow)
    window._config = SimpleNamespace(
        known_ble_devices={},
        sensor_addresses={},
        intervals_api_key="api-key",
        intervals_athlete_id="athlete-id",
        profile_source="intervals_icu",
        weight_kg=85.7,
        ftp=250,
        manual_weight_kg=80.0,
        manual_ftp=220,
        intervals_weight_kg=85.7,
        intervals_ftp=250,
        ui_language="en",
    )
    window._ui_language = "en"
    window._sensor_selector = _FakeSelector()
    window._sensor_reader = _FakeReader()
    window._scan_seen_devices = {}
    window._scan_auto_connect = False
    window._scan_pending_sources = set()
    window._scan_active = False
    window._scan_timeout_after_id = None
    window._qz_status_label = SimpleNamespace(configure=lambda **_kwargs: None)
    window._profile_source_var = _FakeVar("Intervals.icu")
    window._active_profile_source = "intervals_icu"
    window._weight_var = _FakeVar(85.7)
    window._ftp_var = _FakeVar(250)
    window._intervals_api_key_entry = _FakeEntry("api-key")
    window._intervals_athlete_id_entry = _FakeEntry("athlete-id")
    window._workout_loader = _FakeWorkoutLoader()
    window._weight_entry = _FakeWidget()
    window._ftp_entry = _FakeWidget()
    window._weight_value_label = _FakeWidget()
    window._ftp_value_label = _FakeWidget()
    window._profile_sync_status_label = _FakeWidget()
    window.profile_changed = Signal(float, int)
    window.language_changed = Signal(str)
    scheduled = []
    cancelled = []
    window.after = lambda ms, callback: scheduled.append((ms, callback)) or f"after-{len(scheduled)}"
    window.after_cancel = lambda timer_id: cancelled.append(timer_id)
    monkeypatch.setattr(MainWindow, "_scan_qz_wifi", lambda self: None)
    return window, scheduled, cancelled


def test_main_window_scan_watchdog_reenables_button_when_qz_does_not_finish(monkeypatch):
    window, scheduled, _cancelled = _window_stub(monkeypatch)

    MainWindow._start_sensor_scan(window)

    assert window._scan_active is True
    assert window._sensor_reader.scan_count == 1
    assert window._sensor_selector.scanning == [True]

    scheduled[-1][1]()

    assert window._scan_active is False
    assert window._scan_pending_sources == set()
    assert window._sensor_selector.scan_complete_count == 1
    assert window._sensor_selector.statuses[-1][0].startswith("Scan timed out")


def test_main_window_ignores_second_scan_while_scan_is_active(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)

    MainWindow._start_sensor_scan(window)
    MainWindow._start_sensor_scan(window)

    assert window._sensor_reader.scan_count == 1
    assert window._sensor_selector.statuses[-1] == ("Scan already in progress...", "gray")


def test_main_window_qz_terminal_status_completes_scan(monkeypatch):
    window, _scheduled, cancelled = _window_stub(monkeypatch)

    MainWindow._start_sensor_scan(window)
    MainWindow._on_qz_connection_status(window, "QZ Wi-Fi indisponível: zeroconf não instalado")
    MainWindow._on_scan_complete(window)

    assert window._scan_active is False
    assert window._sensor_selector.scan_complete_count == 1
    assert cancelled == ["after-1"]


def test_main_window_qz_busy_status_completes_scan(monkeypatch):
    window, _scheduled, cancelled = _window_stub(monkeypatch)

    MainWindow._start_sensor_scan(window)
    MainWindow._on_qz_connection_status(window, "QZ Wi-Fi ocupado; scan em andamento")
    MainWindow._on_scan_complete(window)

    assert window._scan_active is False
    assert window._sensor_selector.scan_complete_count == 1
    assert cancelled == ["after-1"]


def test_main_window_qz_found_status_completes_scan(monkeypatch):
    window, _scheduled, cancelled = _window_stub(monkeypatch)

    MainWindow._start_sensor_scan(window)
    MainWindow._on_qz_connection_status(window, "QZ Wi-Fi encontrado: 2 fonte(s) disponível(is)")
    MainWindow._on_scan_complete(window)

    assert window._scan_active is False
    assert window._sensor_selector.scan_complete_count == 1
    assert cancelled == ["after-1"]


def test_main_window_disconnects_qz_android_websocket_as_network_device(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)

    MainWindow._on_disconnect_device_requested(window, "qz-ws:192.168.1.50:34107")

    assert window._sensor_reader.network_disconnects == ["qz-ws:192.168.1.50:34107"]
    assert window._sensor_reader.ble_disconnects == []


def test_main_window_deduplicates_rotating_ble_known_devices(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    first = SimpleNamespace(
        address="AA:BB",
        name="Wahoo HRM",
        service_type="hr",
        compatibility_hint="",
        compatibility_profile="",
        detect_service_type=lambda: "hr",
    )
    second = SimpleNamespace(
        address="CC:DD",
        name="Wahoo HRM",
        service_type="hr",
        compatibility_hint="",
        compatibility_profile="",
        detect_service_type=lambda: "hr",
    )

    MainWindow._remember_known_device(window, first)
    MainWindow._remember_known_device(window, second)

    assert list(window._config.known_ble_devices) == ["CC:DD"]


def test_main_window_keeps_qz_virtual_dircon_devices_separate(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    kickr = SimpleNamespace(
        address="qz-dircon:192.168.1.50:36866:KICKR",
        name="QZ Wahoo KICKR",
        service_type="qz_dircon",
        compatibility_hint="QZ Wi-Fi / Wahoo DIRCON",
        compatibility_profile="qz_dircon",
        host="192.168.1.50",
        port=36866,
        serial_number="",
        mac_address="",
        source_type="qz_dircon",
    )
    hrm = SimpleNamespace(
        address="qz-dircon:192.168.1.50:36867:HRM",
        name="QZ Wahoo HRM",
        service_type="qz_dircon",
        compatibility_hint="QZ Wi-Fi / Wahoo DIRCON",
        compatibility_profile="qz_dircon",
        host="192.168.1.50",
        port=36867,
        serial_number="",
        mac_address="",
        source_type="qz_dircon",
    )

    MainWindow._on_network_device_found(window, kickr)
    MainWindow._on_network_device_found(window, hrm)

    assert kickr.address in window._config.known_ble_devices
    assert hrm.address in window._config.known_ble_devices


def test_main_window_startup_sync_runs_only_for_intervals_source(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)

    MainWindow._sync_intervals_on_startup(window)

    assert window._workout_loader.credentials == [("api-key", "athlete-id")]
    assert window._workout_loader.fetch_count == 1

    window._profile_source_var.set("Manual")
    MainWindow._sync_intervals_on_startup(window)

    assert window._workout_loader.fetch_count == 1


def test_main_window_save_intervals_credentials_switches_source_and_syncs(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)

    window._profile_source_var.set("Manual")

    MainWindow._save_and_sync_intervals_credentials(window)

    assert window._profile_source_var.get() == "Intervals.icu"
    assert window._config.profile_source == "intervals_icu"
    assert window._workout_loader.credentials == [("api-key", "athlete-id")]
    assert window._workout_loader.fetch_count == 1
    assert window._profile_sync_status_label.configures[-1]["text"] == "Syncing Intervals.icu..."


def test_main_window_profile_source_toggles_entries_and_readonly_labels(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    window._weight_var = _FakeVar(85.7)
    window._ftp_var = _FakeVar(250)

    MainWindow._on_profile_source_changed(window, "Intervals.icu")

    assert window._weight_entry.grid_remove_count == 1
    assert window._ftp_entry.grid_remove_count == 1
    assert window._weight_value_label.grid_count == 1
    assert window._ftp_value_label.grid_count == 1
    assert window._weight_value_label.configures[-1]["text"] == "85.7 kg"
    assert window._ftp_value_label.configures[-1]["text"] == "250 W"

    MainWindow._on_profile_source_changed(window, "Manual")

    assert window._weight_value_label.grid_remove_count == 1
    assert window._ftp_value_label.grid_remove_count == 1
    assert window._weight_entry.grid_count == 1
    assert window._ftp_entry.grid_count == 1
    assert window._weight_entry.configures[-1]["state"] == "normal"
    assert window._ftp_entry.configures[-1]["state"] == "normal"


def test_main_window_intervals_profile_sync_updates_config_loader_and_emits(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    emitted = []
    window._weight_var = _FakeVar(75.0)
    window._ftp_var = _FakeVar(250)
    window.profile_changed.connect(lambda weight, ftp: emitted.append((weight, ftp)))

    MainWindow._on_intervals_profile_synced(
        window,
        SimpleNamespace(weight_kg=85.7, ftp=250),
    )

    assert window._weight_var.get() == 85.7
    assert window._ftp_var.get() == 250
    assert window._config.weight_kg == 85.7
    assert window._config.ftp == 250
    assert window._workout_loader.ftp == 250
    assert emitted == [(85.7, 250)]
    assert window._weight_value_label.configures[-1]["text"] == "85.7 kg"
    assert window._ftp_value_label.configures[-1]["text"] == "250 W"
    assert window._profile_sync_status_label.configures[-1]["text"] == "Profile updated: 85.7kg, 250w"


def test_main_window_intervals_profile_sync_reports_missing_weight_and_ftp(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    window._weight_var = _FakeVar(75.0)
    window._ftp_var = _FakeVar(250)

    MainWindow._on_intervals_profile_synced(
        window,
        SimpleNamespace(weight_kg=None, ftp=None),
    )

    assert window._weight_var.get() == 85.7
    assert window._ftp_var.get() == 250
    assert window._profile_sync_status_label.configures[-1]["text"] == "Intervals.icu did not return weight/FTP."


def test_main_window_toggle_language_persists_and_updates_children(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    titles = []
    window.title = lambda text: titles.append(text)
    window._language_button = _FakeWidget()

    MainWindow._toggle_ui_language(window)

    assert window._ui_language == "pt"
    assert window._config.ui_language == "pt"
    assert window._language_button.configures[-1]["text"] == "EN"
    assert window._workout_loader.language == "pt"
    assert titles[-1] == "Cycling Overlay - Configuração"


def test_main_window_switching_profiles_keeps_manual_and_intervals_separate(monkeypatch):
    window, _scheduled, _cancelled = _window_stub(monkeypatch)
    emitted = []
    window.profile_changed.connect(lambda weight, ftp: emitted.append((weight, ftp)))

    window._profile_source_var.set("Manual")
    window._weight_var.set(92.0)
    window._ftp_var.set(310)
    window._active_profile_source = "manual"

    MainWindow._on_profile_source_changed(window, "Intervals.icu")

    assert window._config.manual_weight_kg == 92.0
    assert window._config.manual_ftp == 310
    assert window._weight_var.get() == 85.7
    assert window._ftp_var.get() == 250
    assert emitted[-1] == (85.7, 250)

    MainWindow._on_profile_source_changed(window, "Manual")

    assert window._weight_var.get() == 92.0
    assert window._ftp_var.get() == 310
    assert emitted[-1] == (92.0, 310)
