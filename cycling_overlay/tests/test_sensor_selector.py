from app.ui.sensor_selector import SensorSelector
from app.sensors.scanner import ScannedDevice


class _FakeButton:
    def __init__(self):
        self.state = "normal"

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


class _FakeLabel:
    def __init__(self):
        self.text = ""
        self.text_color = ""

    def configure(self, **kwargs):
        self.text = kwargs.get("text", self.text)
        self.text_color = kwargs.get("text_color", self.text_color)


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
