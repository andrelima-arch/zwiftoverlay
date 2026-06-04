from app.core.events import EventLoop
from main import CyclingOverlayApp


class _FakeWindow:
    def __init__(self):
        self.save_count = 0
        self.quit_count = 0
        self.destroy_count = 0

    def save_config(self):
        self.save_count += 1

    def quit(self):
        self.quit_count += 1

    def destroy(self):
        self.destroy_count += 1


class _FakeStopper:
    def __init__(self):
        self.stop_count = 0

    def stop(self):
        self.stop_count += 1


class _FakeEventLoop:
    def __init__(self):
        self.clear_count = 0

    def clear_root(self):
        self.clear_count += 1


def test_app_close_stops_workers_destroys_windows_and_exits_mainloop(monkeypatch):
    fake_loop = _FakeEventLoop()
    monkeypatch.setattr(EventLoop, "get", classmethod(lambda cls: fake_loop))

    app = object.__new__(CyclingOverlayApp)
    app._closing = False
    app.main_window = _FakeWindow()
    app.overlay = _FakeWindow()
    app.root = _FakeWindow()
    app.workout_engine = _FakeStopper()
    app.sensor_reader = _FakeStopper()

    CyclingOverlayApp._on_close(app)
    CyclingOverlayApp._on_close(app)

    assert app.main_window.save_count == 1
    assert app.workout_engine.stop_count == 1
    assert app.sensor_reader.stop_count == 1
    assert app.overlay.quit_count == 1
    assert app.overlay.destroy_count == 1
    assert app.main_window.quit_count == 1
    assert app.main_window.destroy_count == 1
    assert app.root.quit_count == 1
    assert app.root.destroy_count == 1
    assert fake_loop.clear_count == 1
