from pydantic import BaseModel


class SensorData(BaseModel):
    power: int | None = None
    cadence: int | None = None
    heart_rate: int | None = None

    @property
    def is_stopped(self) -> bool:
        if self.power is not None and self.power == 0:
            return True
        if self.heart_rate is not None and self.heart_rate < 40:
            return True
        return False

    @property
    def is_connected(self) -> bool:
        return self.power is not None or self.cadence is not None or self.heart_rate is not None