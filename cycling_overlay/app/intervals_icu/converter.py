import logging

from app.models.workout import Workout, WorkoutInterval

logger = logging.getLogger(__name__)


def convert_workout_doc(workout_doc: dict, title: str = "", ftp: int | None = None) -> Workout:
    if not workout_doc or "steps" not in workout_doc:
        return Workout(title=title, intervals=[])

    intervals = _convert_steps(workout_doc["steps"], ftp)
    return Workout(title=title, intervals=intervals)


def _convert_steps(steps: list[dict], ftp: int | None = None) -> list[WorkoutInterval]:
    result: list[WorkoutInterval] = []
    for step in steps:
        reps = step.get("reps")
        if reps and "steps" in step:
            sub_steps = step.get("steps", [])
            sub_intervals = _convert_steps(sub_steps, ftp)
            for i in range(reps):
                for si in sub_intervals:
                    result.append(si.model_copy(update={
                        "repeat_total": reps,
                        "repeat_index": i + 1 if reps > 1 else None,
                    }))
        else:
            interval = _convert_single_step(step, ftp)
            if interval:
                result.append(interval)
    return result


def _convert_single_step(step: dict, ftp: int | None = None) -> WorkoutInterval | None:
    name = step.get("text", step.get("name", "Interval"))
    duration = step.get("duration")
    if duration is None:
        return None

    duration_seconds = int(duration)

    interval_type = "steady"
    if step.get("warmup"):
        interval_type = "ramp"
    elif step.get("cooldown"):
        interval_type = "ramp"
    elif step.get("maxeffort"):
        interval_type = "sprint"

    power_min, power_max = _extract_power(step, ftp)
    cadence_target = _extract_cadence(step)

    if step.get("ramp"):
        interval_type = "ramp"

    return WorkoutInterval(
        name=name,
        duration_seconds=duration_seconds,
        power_min=power_min,
        power_max=power_max,
        cadence_target=cadence_target,
        type=interval_type,
    )


def _extract_power(step: dict, ftp: int | None = None) -> tuple[int | None, int | None]:
    power = step.get("power")
    if power is None:
        return None, None

    if isinstance(power, dict):
        units = power.get("units", "")
        if units == "%ftp" and ftp:
            pct_start = power.get("start")
            pct_end = power.get("end", power.get("value"))
            value = power.get("value")

            if pct_start is not None and pct_end is not None and pct_start != pct_end:
                return int(ftp * pct_start / 100), int(ftp * pct_end / 100)
            elif value is not None:
                pw = int(ftp * value / 100)
                return pw, pw

        elif units == "w":
            start = power.get("start")
            end = power.get("end", power.get("value"))
            value = power.get("value")

            if start is not None and end is not None and start != end:
                return int(start), int(end)
            elif value is not None:
                pw = int(value)
                return pw, pw

    elif isinstance(power, (int, float)):
        return int(power), int(power)

    return None, None


def _extract_cadence(step: dict) -> int | None:
    cadence = step.get("cadence")
    if cadence is None:
        return None
    if isinstance(cadence, dict):
        value = cadence.get("value")
        return int(value) if value is not None else None
    if isinstance(cadence, (int, float)):
        return int(cadence)
    return None