from enum import Enum

from pydantic import BaseModel

from app.models.sensor_data import SensorData
from app.models.workout import WorkoutInterval


class EngineState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    BETWEEN_INTERVALS = "between_intervals"
    FINISHED = "finished"


class AppState(BaseModel):
    engine_state: EngineState = EngineState.IDLE
    sensor_data: SensorData = SensorData()
    current_interval: WorkoutInterval | None = None
    interval_elapsed_seconds: int = 0
    interval_progress_percent: float = 0.0
    current_target_power: int | None = None
    weight_kg: float | None = None
    ftp: int | None = None
    w_per_kg: float | None = None

    model_config = {"arbitrary_types_allowed": True}