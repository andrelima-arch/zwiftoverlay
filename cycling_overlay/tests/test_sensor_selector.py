from types import SimpleNamespace

from app.ui.sensor_selector import SensorSelector
from app.sensors.scanner import ScannedDevice


class _FakeButton:
    def __init__(self, *args, **kwargs):
        self.state = "normal"
        self.args = args
        self.kwargs = kwargs

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]

    def pack(self, **_kwargs):
        pass

    def destroy(self):
        pass


class _FakeFrame:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.children = []
        self.packed = False
        self.destroyed = False
        self.bindings = {}

    def configure(self, **kwargs):
        self.kwargs.update(kwargs)

    def pack(self, **kwargs):
        self.packed = True
        self.pack_kwargs = kwargs

    def grid(self, **kwargs):
        self.grid_kwargs = kwargs

    def bind(self, event, callback):
        self.bindings[event] = callback

    def destroy(self):
        self.destroyed = True


class _FakeLabel:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.text = kwargs.get("text", "")
        self.text_color = kwargs.get("text_color", "")
        self.packed = False
        self.bindings = {}

    def configure(self, **kwargs):
        self.text = kwargs.get("text", self.text)
        self.text_color = kwargs.get("text_color", self.text_color)
        self.kwargs.update(kwargs)

    def pack(self, **kwargs):
        self.packed = True
        self.pack_kwargs = kwargs

    def pack_forget(self):
        self.packed = False

    def bind(self, event, callback):
        self.bindings[event] = callback


def _selector_stub(monkeypatch):
    selector = object.__new__(SensorSelector)
    selector._language = "en"
    selector._hr_address = None
    selector._power_address = None
    selector._csc_address = None
    selector._ftms_address = None
    selector._selected_sensor_details = {}
    selector._scanned_devices = {}
    selector._device_buttons = {}
    selector._device_button_groups = {}
    selector._known_devices = {}
    selector._connection_states = {}
    selector._scan_generation = 0
    selector._device_seen_generation = {}
    selector._status_label = _FakeLabel()
    selector._hr_label = _FakeLabel()
    selector._power_label = _FakeLabel()
    selector._csc_label = _FakeLabel()
    selector._ftms_label = _FakeLabel()
    selector._scan_buttons = (_FakeButton(),)
    rendered = []
    monkeypatch.setattr(
        SensorSelector,
        "_render_device_button",
        lambda self, address, display, known, saved, service_type: rendered.append(
            (address, display, service_type)
        ),
    )
    return selector, rendered


def test_sensor_selector_treats_verbose_qz_connected_status_as_connected():
    selector = object()

    assert SensorSelector._status_category(selector, "Connected QZ DIRCON QZ Wahoo") == "connected"
    assert SensorSelector._status_category(selector, "Connecting QZ DIRCON 192.168.1.42:36866") == "connecting"
    assert SensorSelector._status_category(selector, "Queued...") == "queued"


def test_sensor_selector_scan_keeps_available_devices_and_marks_stale(monkeypatch):
    selector, rendered = _selector_stub(monkeypatch)
    hrm = ScannedDevice("HRM", "Wahoo HRM", ["180d"], service_type="hr")
    trainer = ScannedDevice("KICKR", "Wahoo KICKR", ["1826"], service_type="ftms")

    selector.start_scan()
    selector.add_device(hrm)
    selector.add_device(trainer)
    selector.scan_complete()

    selector.start_scan()
    selector.add_device(trainer)
    selector.scan_complete()

    assert "HRM" in selector._scanned_devices
    assert "KICKR" in selector._scanned_devices
    assert selector._connection_states["HRM"] == "Stale"
    assert rendered[-1][0] == "HRM"


def test_sensor_selector_scan_never_marks_connected_device_stale(monkeypatch):
    selector, _rendered = _selector_stub(monkeypatch)
    trainer = ScannedDevice("KICKR", "Wahoo KICKR", ["1826"], service_type="ftms")

    selector.start_scan()
    selector.add_device(trainer)
    selector.update_connection_status("KICKR", "Connected")
    selector.scan_complete()

    selector.start_scan()
    selector.scan_complete()

    assert selector._connection_states["KICKR"] == "Connected"


def test_sensor_selector_translates_empty_assigned_labels(monkeypatch):
    selector, _rendered = _selector_stub(monkeypatch)

    SensorSelector._refresh_assigned_labels(selector)

    assert selector._power_label.text == "Power: none"

    selector._language = "pt"
    SensorSelector._refresh_assigned_labels(selector)

    assert selector._power_label.text == "Potência: nenhum"


def test_sensor_selector_device_rows_align_text_left(monkeypatch):
    frames = []
    labels = []

    class FakeFrame(_FakeFrame):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            frames.append(self)

    class FakeLabel(_FakeLabel):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            labels.append(self)

    monkeypatch.setattr("app.ui.sensor_selector.ctk.CTkFrame", FakeFrame)
    monkeypatch.setattr("app.ui.sensor_selector.ctk.CTkLabel", FakeLabel)
    monkeypatch.setattr("app.ui.sensor_selector.ctk.CTkFont", lambda **kwargs: kwargs)
    selector = object.__new__(SensorSelector)
    selector._connection_states = {}
    selector._connected_list = object()
    selector._available_group_frames = {
        "saved": object(),
        "queued": object(),
        "recent": object(),
        "unknown": object(),
    }
    selector._available_group_placeholders = {
        "saved": _FakeLabel(text="-"),
        "queued": _FakeLabel(text="-"),
        "recent": _FakeLabel(text="-"),
        "unknown": _FakeLabel(text="-"),
    }
    selector._device_buttons = {}
    selector._device_button_groups = {}

    SensorSelector._render_device_button(
        selector,
        "qz-ws:192.168.1.50:34107",
        "QZ Android 192.168.1.50 [QZ Wi-Fi / Android app] [Recent]",
        known=False,
        saved=False,
        service_type="qz_websocket",
    )

    assert frames[0].kwargs["fg_color"] == "#4a4a4a"
    assert labels[0].kwargs["anchor"] == "w"
    assert labels[0].kwargs["justify"] == "left"
    assert labels[0].text == "QZ Android 192.168.1.50"
    assert labels[1].kwargs["anchor"] == "w"
    assert labels[1].kwargs["justify"] == "left"


def test_sensor_selector_groups_available_devices_by_state():
    selector = object.__new__(SensorSelector)
    selector._connection_states = {
        "KICKR": "Queued...",
    }

    assert SensorSelector._device_group(selector, "HRM", known=False, saved=True, service_type="hr") == "saved"
    assert SensorSelector._device_group(selector, "KICKR", known=True, saved=False, service_type="ftms") == "queued"
    assert SensorSelector._device_group(selector, "CAD", known=False, saved=False, service_type="csc") == "recent"
    assert SensorSelector._device_group(selector, "UNK", known=False, saved=False, service_type="unknown") == "unknown"


def test_sensor_selector_group_placeholders_are_visible_when_empty():
    selector = object.__new__(SensorSelector)
    selector._device_button_groups = {}
    selector._available_group_placeholders = {
        "saved": _FakeLabel(text="-"),
        "queued": _FakeLabel(text="-"),
        "recent": _FakeLabel(text="-"),
        "unknown": _FakeLabel(text="-"),
    }

    SensorSelector._refresh_all_group_placeholders(selector)

    assert selector._available_group_placeholders["saved"].packed is True
    assert selector._available_group_placeholders["queued"].packed is True


def test_sensor_selector_deduplicates_rotating_ble_but_keeps_qz_virtual_devices(monkeypatch):
    selector, _rendered = _selector_stub(monkeypatch)
    first_hrm = ScannedDevice("AA:BB", "Wahoo HRM", ["180d"], service_type="hr")
    second_hrm = ScannedDevice("CC:DD", "Wahoo HRM", ["180d"], service_type="hr")

    selector.add_device(first_hrm)
    selector.add_device(second_hrm)

    assert list(selector._scanned_devices) == ["CC:DD"]

    kickr = SimpleNamespace(
        address="qz-dircon:192.168.1.50:36866:KICKR",
        name="QZ Wahoo KICKR",
        service_type="qz_dircon",
        host="192.168.1.50",
        port=36866,
        compatibility_profile="qz_dircon",
        compatibility_hint="QZ Wi-Fi / Wahoo DIRCON",
        display_name="QZ Wahoo KICKR",
        detect_service_type=lambda: "qz_dircon",
    )
    hrm = SimpleNamespace(
        address="qz-dircon:192.168.1.50:36867:HRM",
        name="QZ Wahoo HRM",
        service_type="qz_dircon",
        host="192.168.1.50",
        port=36867,
        compatibility_profile="qz_dircon",
        compatibility_hint="QZ Wi-Fi / Wahoo DIRCON",
        display_name="QZ Wahoo HRM",
        detect_service_type=lambda: "qz_dircon",
    )

    selector.add_device(kickr)
    selector.add_device(hrm)

    assert kickr.address in selector._scanned_devices
    assert hrm.address in selector._scanned_devices
