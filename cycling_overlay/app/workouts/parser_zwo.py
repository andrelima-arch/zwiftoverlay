from pathlib import Path
import xml.etree.ElementTree as ET

from app.models.workout import Workout, WorkoutInterval


def parse_zwo_file(path: str | Path, ftp: int | None = None) -> Workout:
    file_path = Path(path)
    root = ET.parse(file_path).getroot()
    title = _find_text(root, "name") or file_path.stem
    workout_node = _find_child(root, "workout")
    if workout_node is None:
        return Workout(title=title, intervals=[])

    intervals: list[WorkoutInterval] = []
    for node in list(workout_node):
        intervals.extend(_parse_node(node, ftp))

    return Workout(title=title, intervals=intervals)


def find_zwo_files(folder: str | Path) -> list[Path]:
    base = Path(folder)
    if not base.exists() or not base.is_dir():
        return []
    return sorted(base.rglob("*.zwo"), key=lambda p: (p.name.lower(), str(p).lower()))


def _parse_node(node: ET.Element, ftp: int | None) -> list[WorkoutInterval]:
    tag = _strip_ns(node.tag)
    if tag == "IntervalsT":
        return _parse_intervals_t(node, ftp)
    interval = _parse_single_interval(node, ftp)
    return [interval] if interval is not None else []


def _parse_single_interval(node: ET.Element, ftp: int | None) -> WorkoutInterval | None:
    tag = _strip_ns(node.tag)
    duration = _duration(node)
    if duration <= 0:
        return None

    power_min, power_max = _power_range(node, ftp)
    interval_type = "steady"
    name = _name_for_node(node, tag)

    if tag in {"Warmup", "Cooldown", "Ramp"} or power_min != power_max:
        interval_type = "ramp"
    if tag == "FreeRide":
        power_min = None
        power_max = None
    if tag == "Cooldown":
        interval_type = "ramp"

    return WorkoutInterval(
        name=name,
        duration_seconds=duration,
        power_min=power_min,
        power_max=power_max,
        cadence_target=_cadence(node),
        type=interval_type,
    )


def _parse_intervals_t(node: ET.Element, ftp: int | None) -> list[WorkoutInterval]:
    repeat = _int_attr(node, "Repeat", 1)
    on_duration = _int_float_attr(node, "OnDuration", 0)
    off_duration = _int_float_attr(node, "OffDuration", 0)
    on_power = _power_value(node, ftp, "OnPower")
    off_power = _power_value(node, ftp, "OffPower")
    cadence = _cadence(node)
    cadence_rest = _int_attr(node, "CadenceRest", cadence)

    intervals: list[WorkoutInterval] = []
    for i in range(repeat):
        if on_duration > 0:
            intervals.append(WorkoutInterval(
                name=_attr(node, "Name") or "Interval",
                duration_seconds=on_duration,
                power_min=on_power,
                power_max=on_power,
                cadence_target=cadence,
                type="steady",
                repeat_total=repeat if repeat > 1 else None,
                repeat_index=i + 1 if repeat > 1 else None,
            ))
        if off_duration > 0:
            intervals.append(WorkoutInterval(
                name="Recovery",
                duration_seconds=off_duration,
                power_min=off_power,
                power_max=off_power,
                cadence_target=cadence_rest,
                type="recovery",
                repeat_total=repeat if repeat > 1 else None,
                repeat_index=i + 1 if repeat > 1 else None,
            ))
    return intervals


def _name_for_node(node: ET.Element, tag: str) -> str:
    text_event = node.find("textevent")
    if text_event is not None:
        message = _attr(text_event, "message")
        if message:
            return message
    return _attr(node, "Name") or {
        "Warmup": "Warmup",
        "Cooldown": "Cooldown",
        "SteadyState": "Steady",
        "Ramp": "Ramp",
        "FreeRide": "Free Ride",
    }.get(tag, tag)


def _power_range(node: ET.Element, ftp: int | None) -> tuple[int | None, int | None]:
    low = _power_value(node, ftp, "PowerLow")
    high = _power_value(node, ftp, "PowerHigh")
    if low is not None or high is not None:
        return low, high
    power = _power_value(node, ftp, "Power")
    return power, power


def _power_value(node: ET.Element, ftp: int | None, attr: str) -> int | None:
    raw = _attr(node, attr)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 2.5 and ftp:
        return int(ftp * value)
    return int(value)


def _duration(node: ET.Element) -> int:
    for attr in ("Duration", "duration"):
        value = _int_float_attr(node, attr, 0)
        if value:
            return value
    return 0


def _cadence(node: ET.Element) -> int | None:
    return _int_attr(node, "Cadence")


def _attr(node: ET.Element, key: str) -> str | None:
    for candidate in (key, key.lower(), key.upper()):
        value = node.attrib.get(candidate)
        if value is not None:
            return value
    return None


def _int_attr(node: ET.Element, key: str, default: int | None = None) -> int | None:
    value = _attr(node, key)
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _int_float_attr(node: ET.Element, key: str, default: int = 0) -> int:
    value = _attr(node, key)
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _find_text(root: ET.Element, name: str) -> str:
    node = _find_child(root, name)
    return node.text.strip() if node is not None and node.text else ""


def _find_child(root: ET.Element, name: str) -> ET.Element | None:
    for child in list(root):
        if _strip_ns(child.tag) == name:
            return child
    return None


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]
