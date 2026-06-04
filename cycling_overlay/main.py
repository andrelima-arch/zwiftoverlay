import logging
import sys

import customtkinter as ctk

from app.core.config_manager import ConfigManager
from app.core.events import EventLoop
from app.core.state_manager import StateManager
from app.core.workout_engine import WorkoutEngine
from app.models.app_state import EngineState
from app.models.sensor_data import SensorData
from app.sensors.reader import SensorReader
from app.ui.main_window import MainWindow
from app.ui.overlay_window import OverlayWindow

logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CyclingOverlayApp:
    def __init__(self) -> None:
        self._closing = False
        self.root = ctk.CTk()
        self.root.withdraw()
        EventLoop.get().set_root(self.root)

        self.config = ConfigManager()
        self.state_manager = StateManager()
        self.workout_engine = WorkoutEngine()
        self.sensor_reader = SensorReader()

        self.overlay = OverlayWindow(language=self.config.ui_language)
        self.main_window = MainWindow(self.config, self.sensor_reader)
        self.main_window.protocol("WM_DELETE_WINDOW", self._on_close)

        self._connect_signals()

    def _connect_signals(self) -> None:
        mw = self.main_window

        mw.start_button.configure(command=self._on_start)
        mw.stop_button.configure(command=self._on_stop)

        self.sensor_reader.sensor_data_updated.connect(self._on_sensor_data)
        mw.profile_changed.connect(self._on_profile_changed)
        mw.language_changed.connect(self.overlay.set_language)

        self.state_manager.state_changed.connect(self._on_state_changed)
        self.workout_engine.interval_changed.connect(self._on_interval_changed)
        self.workout_engine.progress_tick.connect(self._on_progress_tick)
        self.workout_engine.state_changed.connect(self._on_engine_state_changed)

    def _on_start(self) -> None:
        self._start_workout()
        self.sensor_reader.start()
        sensors = self.main_window.sensor_selector.get_selected_sensors()
        for service, sensor in sensors.items():
            if isinstance(sensor, dict):
                address = sensor.get("address")
                details = sensor
            else:
                address = sensor
                details = None
            if address:
                self.sensor_reader.connect_device(str(address), service, details)

    def _start_workout(self) -> None:
        self.main_window.save_config()
        self.state_manager.set_weight(self.main_window.weight_kg)
        self.state_manager.set_ftp(self.main_window.ftp)
        self.workout_engine.load_workout(self.main_window.selected_workout)
        self.workout_engine.start()
        self.overlay.deiconify()
        self.main_window.set_running(True)

    def _on_stop(self) -> None:
        try:
            self.workout_engine.stop()
        except Exception:
            logger.exception("Error stopping workout engine on close")
        try:
            self.sensor_reader.stop()
        except Exception:
            logger.exception("Error stopping sensor reader on close")
        self.overlay.withdraw()
        self.main_window.set_running(False)

    def _on_sensor_data(self, data) -> None:
        if isinstance(data, SensorData):
            self.state_manager.update_sensor_data(data)
            self.workout_engine.update_sensor(data)

    def _on_state_changed(self, state) -> None:
        self.overlay.update_state(state)

    def _on_profile_changed(self, weight_kg: float, ftp: int) -> None:
        self.state_manager.set_weight(weight_kg)
        self.state_manager.set_ftp(ftp)
        if self.workout_engine.has_workout:
            self.workout_engine.replace_workout_preserving_progress(
                self.main_window.selected_workout
            )

    def _on_interval_changed(self, interval, elapsed, progress) -> None:
        self.state_manager.set_current_interval(interval, elapsed, progress)

    def _on_progress_tick(self, elapsed, progress) -> None:
        if self.workout_engine.current_interval:
            self.state_manager.set_current_interval(
                self.workout_engine.current_interval, elapsed, progress
            )

    def _on_engine_state_changed(self, state: EngineState) -> None:
        self.state_manager.set_engine_state(state)
        if state == EngineState.FINISHED:
            self.sensor_reader.stop()
            self.main_window.set_running(False)

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True

        try:
            self.main_window.save_config()
        except Exception:
            logger.exception("Error saving config on close")

        self.workout_engine.stop()
        self.sensor_reader.stop()

        for window in (self.overlay, self.main_window):
            try:
                window.quit()
            except Exception:
                pass
            try:
                window.destroy()
            except Exception:
                pass

        EventLoop.get().clear_root()
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> int:
        self.main_window.mainloop()
        return 0


def main() -> None:
    app = CyclingOverlayApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
