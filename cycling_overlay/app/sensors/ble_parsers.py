"""BLE measurement parsers adapted from Bluetooth SIG specs and QZ behavior."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PowerMeasurement:
    power: int | None = None
    flags: int = 0
    wheel_revs: int | None = None
    wheel_event_time: int | None = None
    crank_revs: int | None = None
    crank_event_time: int | None = None
    has_wheel_data: bool = False
    has_crank_data: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class FtmsMeasurement:
    values: dict[str, int] = field(default_factory=dict)
    flags: int = 0
    has_instant_cadence: bool = False
    has_average_cadence: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class CscMeasurement:
    crank_revs: int | None = None
    crank_event_time: int | None = None
    has_crank_data: bool = False
    truncated: bool = False


def parse_heart_rate(data: bytes | bytearray) -> int | None:
    if len(data) < 2:
        return None
    flags = data[0]
    if flags & 0x01:
        if len(data) < 3:
            return None
        return int.from_bytes(data[1:3], "little")
    return data[1]


def parse_power_measurement(data: bytes | bytearray) -> PowerMeasurement:
    if len(data) < 4:
        return PowerMeasurement(truncated=True)

    flags = int.from_bytes(data[0:2], "little")
    power = int.from_bytes(data[2:4], "little", signed=True)
    offset = 4

    if flags & (1 << 0):
        offset += 1
    if flags & (1 << 2):
        offset += 2

    has_wheel_data = bool(flags & (1 << 4))
    has_crank_data = bool(flags & (1 << 5))
    wheel_revs = None
    wheel_event_time = None
    crank_revs = None
    crank_event_time = None

    if has_wheel_data:
        if offset + 6 > len(data):
            return PowerMeasurement(power=power, flags=flags, has_wheel_data=True, truncated=True)
        wheel_revs = int.from_bytes(data[offset:offset + 4], "little")
        wheel_event_time = int.from_bytes(data[offset + 4:offset + 6], "little")
        offset += 6

    if has_crank_data:
        if offset + 4 > len(data):
            return PowerMeasurement(
                power=power,
                flags=flags,
                wheel_revs=wheel_revs,
                wheel_event_time=wheel_event_time,
                has_wheel_data=has_wheel_data,
                has_crank_data=True,
                truncated=True,
            )
        crank_revs = int.from_bytes(data[offset:offset + 2], "little")
        crank_event_time = int.from_bytes(data[offset + 2:offset + 4], "little")

    return PowerMeasurement(
        power=power,
        flags=flags,
        wheel_revs=wheel_revs,
        wheel_event_time=wheel_event_time,
        crank_revs=crank_revs,
        crank_event_time=crank_event_time,
        has_wheel_data=has_wheel_data,
        has_crank_data=has_crank_data,
    )


def parse_csc_measurement(data: bytes | bytearray) -> CscMeasurement:
    if len(data) < 1:
        return CscMeasurement(truncated=True)

    flags = data[0]
    offset = 1
    if flags & 0x01:
        if offset + 6 > len(data):
            return CscMeasurement(truncated=True)
        offset += 6

    if not flags & 0x02:
        return CscMeasurement()

    if offset + 4 > len(data):
        return CscMeasurement(has_crank_data=True, truncated=True)

    crank_revs = int.from_bytes(data[offset:offset + 2], "little")
    crank_event_time = int.from_bytes(data[offset + 2:offset + 4], "little")
    return CscMeasurement(
        crank_revs=crank_revs,
        crank_event_time=crank_event_time,
        has_crank_data=True,
    )


def parse_ftms_indoor_bike_data(data: bytes | bytearray) -> FtmsMeasurement:
    if len(data) < 2:
        return FtmsMeasurement(truncated=True)

    flags = int.from_bytes(data[0:2], "little")
    offset = 2
    values: dict[str, int] = {}

    if not flags & (1 << 0):
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, truncated=True)
        offset += 2

    if flags & (1 << 1):
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, truncated=True)
        offset += 2

    has_instant_cadence = bool(flags & (1 << 2))
    if has_instant_cadence:
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence=True, truncated=True)
        values["cadence"] = round(int.from_bytes(data[offset:offset + 2], "little") / 2)
        offset += 2

    has_average_cadence = bool(flags & (1 << 3))
    if has_average_cadence:
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, True, True)
        avg_cadence = round(int.from_bytes(data[offset:offset + 2], "little") / 2)
        values.setdefault("cadence", avg_cadence)
        offset += 2

    if flags & (1 << 4):
        if offset + 3 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        offset += 3

    if flags & (1 << 5):
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        offset += 2

    if flags & (1 << 6):
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        values["power"] = int.from_bytes(data[offset:offset + 2], "little", signed=True)
        offset += 2

    if flags & (1 << 7):
        if offset + 2 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        offset += 2

    if flags & (1 << 8):
        if offset + 5 > len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        offset += 5

    if flags & (1 << 9):
        if offset >= len(data):
            return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence, True)
        values["heart_rate"] = data[offset]

    return FtmsMeasurement(values, flags, has_instant_cadence, has_average_cadence)


@dataclass(frozen=True)
class RscMeasurement:
    speed_mps: float | None = None
    cadence: int | None = None
    total_distance: int | None = None
    truncated: bool = False


def parse_rsc_measurement(data: bytes | bytearray) -> RscMeasurement:
    """Parse Running Speed and Cadence measurement (0x2A53)."""
    if len(data) < 3:
        return RscMeasurement(truncated=True)

    flags = data[0]
    offset = 1

    # Instantaneous Speed is always present (uint16, 1/256 m/s)
    if offset + 2 > len(data):
        return RscMeasurement(truncated=True)
    speed_raw = int.from_bytes(data[offset:offset + 2], "little")
    speed_mps = speed_raw / 256.0
    offset += 2

    # Instantaneous Cadence is always present (uint8, 1 rpm)
    if offset + 1 > len(data):
        return RscMeasurement(speed_mps=speed_mps, truncated=True)
    cadence = data[offset]
    offset += 1

    total_distance = None
    if flags & 0x01:
        # Instantaneous Stride Length present (skip 2 bytes)
        offset += 2
    if flags & 0x02:
        # Total Distance present (uint32, meters)
        if offset + 4 <= len(data):
            total_distance = int.from_bytes(data[offset:offset + 4], "little")

    return RscMeasurement(
        speed_mps=round(speed_mps, 2),
        cadence=cadence,
        total_distance=total_distance,
    )
