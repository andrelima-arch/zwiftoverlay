from app.models.sensor_data import SensorData


class FakeSensor:
    def __init__(self) -> None:
        self._readings: list[SensorData] = []
        self._index = 0

    def program(self, readings: list[SensorData]) -> "FakeSensor":
        self._readings = readings
        self._index = 0
        return self

    def read(self) -> SensorData | None:
        if self._index >= len(self._readings):
            return None
        data = self._readings[self._index]
        self._index += 1
        return data

    @staticmethod
    def pedaling(power: int = 180, cadence: int = 88, hr: int = 145) -> SensorData:
        return SensorData(power=power, cadence=cadence, heart_rate=hr)

    @staticmethod
    def stopped() -> SensorData:
        return SensorData(power=0, cadence=0, heart_rate=60)

    @staticmethod
    def no_power(hr: int = 65) -> SensorData:
        return SensorData(power=0, heart_rate=hr)

    @staticmethod
    def low_hr() -> SensorData:
        return SensorData(power=0, cadence=0, heart_rate=35)