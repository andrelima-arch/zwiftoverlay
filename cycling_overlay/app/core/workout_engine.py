import threading
from app.core.events import Signal
from app.models.app_state import EngineState
from app.models.sensor_data import SensorData
from app.models.workout import Workout, WorkoutInterval


STOPPED_TIMEOUT_SECONDS = 30
PAUSE_THRESHOLD_SECONDS = 60
PROGRESS_PAUSE_THRESHOLD = 0.80


class WorkoutEngine:
    interval_changed = Signal(object, int, float)
    state_changed = Signal(object)
    workout_finished = Signal()
    progress_tick = Signal(int, float)

    def __init__(self) -> None:
        self._workout: Workout | None = None
        self._expanded: list[WorkoutInterval] = []
        self._current_index: int = 0
        self._elapsed_in_interval: int = 0
        self._total_elapsed: int = 0
        self._state: EngineState = EngineState.IDLE
        self._last_sensor_data: SensorData | None = None
        self._stopped_seconds: int = 0
        self._running: bool = False
        self._lock = threading.Lock()
        self._timer_id: str | None = None

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def current_interval(self) -> WorkoutInterval | None:
        if 0 <= self._current_index < len(self._expanded):
            return self._expanded[self._current_index]
        return None

    @property
    def current_progress(self) -> float:
        interval = self.current_interval
        if interval and interval.duration_seconds > 0:
            return self._elapsed_in_interval / interval.duration_seconds
        return 0.0

    @property
    def has_workout(self) -> bool:
        return bool(self._expanded)

    def load_workout(self, workout: Workout) -> None:
        self._workout = workout
        self._expanded = workout.expanded_intervals()
        self._current_index = 0
        self._elapsed_in_interval = 0
        self._total_elapsed = 0
        self._stopped_seconds = 0

    def replace_workout_preserving_progress(self, workout: Workout) -> None:
        expanded = workout.expanded_intervals()
        if not expanded:
            return

        self._workout = workout
        previous_index = self._current_index
        previous_elapsed = self._elapsed_in_interval
        self._expanded = expanded
        self._current_index = min(previous_index, len(expanded) - 1)
        interval = self.current_interval
        if interval:
            self._elapsed_in_interval = min(previous_elapsed, max(interval.duration_seconds - 1, 0))
        else:
            self._elapsed_in_interval = 0

        if self._state != EngineState.IDLE and self._state != EngineState.FINISHED:
            self._emit_interval()
            self._emit_progress()

    def start(self) -> None:
        if not self._expanded:
            return
        self._current_index = 0
        self._elapsed_in_interval = 0
        self._total_elapsed = 0
        self._stopped_seconds = 0
        self._set_state(EngineState.RUNNING)
        self._running = True
        self._schedule_tick()
        self._emit_interval()

    def stop(self) -> None:
        self._running = False
        self._cancel_tick()
        self._set_state(EngineState.FINISHED)
        self.workout_finished.emit()

    def update_sensor(self, data: SensorData) -> None:
        self._last_sensor_data = data

    def _schedule_tick(self) -> None:
        from app.core.events import EventLoop
        self._timer_id = EventLoop.get().call_later(1000, self._on_tick)

    def _cancel_tick(self) -> None:
        from app.core.events import EventLoop
        EventLoop.get().cancel(self._timer_id)
        self._timer_id = None

    def _on_tick(self) -> None:
        if not self._running:
            return

        if self._state == EngineState.FINISHED:
            self._running = False
            return

        is_stopped = self._is_user_stopped()

        if self._state == EngineState.RUNNING:
            if is_stopped:
                self._stopped_seconds += 1
                if self._stopped_seconds >= PAUSE_THRESHOLD_SECONDS:
                    if self.current_progress < PROGRESS_PAUSE_THRESHOLD:
                        self._set_state(EngineState.PAUSED)
                        self._emit_progress()
                        self._schedule_tick()
                        return
            else:
                self._stopped_seconds = 0

            self._elapsed_in_interval += 1
            self._total_elapsed += 1

            interval = self.current_interval
            if interval and self._elapsed_in_interval >= interval.duration_seconds:
                if is_stopped and self._has_next_interval():
                    self._elapsed_in_interval = interval.duration_seconds
                    self._emit_progress()
                    self._set_state(EngineState.BETWEEN_INTERVALS)
                    self._schedule_tick()
                    return
                else:
                    self._advance_interval()
                    self._schedule_tick()
                    return

            self._emit_progress()
            self._schedule_tick()

        elif self._state == EngineState.PAUSED:
            if not is_stopped:
                self._stopped_seconds = 0
                self._set_state(EngineState.RUNNING)
            self._schedule_tick()

        elif self._state == EngineState.BETWEEN_INTERVALS:
            if not is_stopped:
                self._stopped_seconds = 0
                self._advance_interval()
            self._schedule_tick()

    def _is_user_stopped(self) -> bool:
        if self._last_sensor_data is None:
            return False
        return self._last_sensor_data.is_stopped

    def _has_next_interval(self) -> bool:
        return self._current_index + 1 < len(self._expanded)

    def _advance_interval(self) -> None:
        self._current_index += 1
        self._elapsed_in_interval = 0
        self._stopped_seconds = 0

        if self._current_index >= len(self._expanded):
            self.stop()
            return

        self._set_state(EngineState.RUNNING)
        self._emit_interval()

    def _set_state(self, state: EngineState) -> None:
        if self._state != state:
            self._state = state
            self.state_changed.emit(state)

    def _emit_interval(self) -> None:
        interval = self.current_interval
        if interval:
            self.interval_changed.emit(interval, self._elapsed_in_interval, 0.0)

    def _emit_progress(self) -> None:
        interval = self.current_interval
        if interval:
            progress = self.current_progress
            self.progress_tick.emit(self._elapsed_in_interval, progress)
            self.interval_changed.emit(interval, self._elapsed_in_interval, progress)
