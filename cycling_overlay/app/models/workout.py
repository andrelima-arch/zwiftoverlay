from typing import Literal

from pydantic import BaseModel


class WorkoutInterval(BaseModel):
    name: str
    duration_seconds: int
    power_min: int | None = None
    power_max: int | None = None
    cadence_target: int | None = None
    type: Literal["steady", "ramp", "sprint", "recovery"] = "steady"
    repeat_index: int | None = None
    repeat_total: int | None = None

    @property
    def target_display(self) -> str:
        if self.power_min is None and self.power_max is None:
            return "---w"
        if self.power_min == self.power_max:
            return f"{self.power_min}w"
        return f"{self.power_min}-{self.power_max}w"

    @property
    def progress_percent(self) -> float:
        return 0.0

    def power_at_elapsed(self, elapsed_seconds: int) -> int | None:
        if self.type != "ramp":
            return self.power_max
        if self.duration_seconds == 0:
            return self.power_min
        progress = min(elapsed_seconds / self.duration_seconds, 1.0)
        if self.power_min is None or self.power_max is None:
            return None
        return int(self.power_min + (self.power_max - self.power_min) * progress)


class Workout(BaseModel):
    title: str = ""
    intervals: list[WorkoutInterval] = []

    def expanded_intervals(self) -> list[WorkoutInterval]:
        result: list[WorkoutInterval] = []
        for interval in self.intervals:
            if interval.repeat_total and interval.repeat_total > 1:
                for i in range(interval.repeat_total):
                    result.append(interval.model_copy(update={
                        "repeat_index": i + 1,
                        "repeat_total": interval.repeat_total,
                    }))
            else:
                result.append(interval)
        return result