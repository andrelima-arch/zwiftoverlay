from app.core.events import Signal
from app.models.app_state import AppState, EngineState
from app.models.sensor_data import SensorData
from app.models.workout import WorkoutInterval


class StateManager:
    state_changed = Signal(object)

    def __init__(self) -> None:
        self._state = AppState()
        self._weight_kg: float | None = None

    @property
    def state(self) -> AppState:
        return self._state

    def update_sensor_data(self, data: SensorData) -> None:
        self._state.sensor_data = data
        self._recalculate_w_per_kg()
        self.state_changed.emit(self._state)

    def set_current_interval(
        self, interval: WorkoutInterval, elapsed: int, progress: float
    ) -> None:
        self._state.current_interval = interval
        self._state.interval_elapsed_seconds = elapsed
        self._state.interval_remaining_seconds = max(0, interval.duration_seconds - elapsed)
        self._state.interval_progress_percent = progress
        if interval.type == "ramp":
            self._state.current_target_power = interval.power_at_elapsed(elapsed)
        else:
            self._state.current_target_power = interval.power_max
        self.state_changed.emit(self._state)

    def set_engine_state(self, state: EngineState) -> None:
        self._state.engine_state = state
        self.state_changed.emit(self._state)

    def set_weight(self, weight_kg: float | None) -> None:
        self._weight_kg = weight_kg
        self._state.weight_kg = weight_kg
        self._recalculate_w_per_kg()
        self.state_changed.emit(self._state)

    def set_ftp(self, ftp: int | None) -> None:
        self._state.ftp = ftp
        self.state_changed.emit(self._state)

    def clear_current_interval(self) -> None:
        self._state.current_interval = None
        self._state.interval_elapsed_seconds = 0
        self._state.interval_remaining_seconds = 0
        self._state.interval_progress_percent = 0.0
        self._state.current_target_power = None
        self.state_changed.emit(self._state)

    def _recalculate_w_per_kg(self) -> None:
        power = self._state.sensor_data.power
        if power is None:
            self._state.w_per_kg = None
            return
        if self._weight_kg is None or self._weight_kg <= 0:
            self._state.w_per_kg = None
            return
        self._state.w_per_kg = round(power / self._weight_kg, 1)
