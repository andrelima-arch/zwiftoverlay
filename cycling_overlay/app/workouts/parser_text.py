import re
from app.models.workout import Workout, WorkoutInterval


LINE_PATTERNS = [
    (r"(?i)^\s*warm\s*up\s*:?\s*(.*)", "Warmup", "ramp"),
    (r"(?i)^\s*cool\s*down\s*:?\s*(.*)", "Cooldown", "ramp"),
    (r"(?i)^\s*endurance\s*(.*)", "Endurance", "steady"),
    (r"(?i)^\s*sprint\s*(.*)", "Sprint", "sprint"),
    (r"(?i)^\s*recovery\s*(.*)", "Recovery", "recovery"),
    (r"(?i)^\s*interval\s*(.*)", "Interval", "steady"),
    (r"(?i)^\s*ramp\s*(.*)", "Ramp", "ramp"),
    (r"(?i)^\s*rest\s*(.*)", "Rest", "recovery"),
]

BLOCK_HEADERS = [
    (r"(?i)^\s*main\s*set\s*(\d+)\s*[x\u00d7]\s*$", "main_set"),
    (r"(?i)^\s*warm\s*up\s*:?\s*$", "warmup_header"),
    (r"(?i)^\s*cool\s*down\s*:?\s*$", "cooldown_header"),
]


def parse_workout_text(text: str, ftp: int | None = None) -> Workout:
    intervals: list[WorkoutInterval] = []
    title = ""
    lines = text.strip().splitlines()

    repeat_total = None
    repeat_buffer: list[WorkoutInterval] = []
    pending_header_name = None
    pending_header_type = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        is_section_header = bool(re.match(r"(?i)^\s*(warm\s*up|cool\s*down|main\s*set)", line))

        if is_section_header:
            if repeat_buffer and repeat_total:
                intervals.extend(_expand_cycle(repeat_buffer, repeat_total))
                repeat_buffer = []
                repeat_total = None

        block_match = _match_block_header(line)
        if block_match:
            name, btype = block_match
            if name == "Main Set":
                repeat_in_line = re.search(r"(\d+)\s*[x\u00d7]", line)
                if repeat_in_line:
                    if repeat_buffer and repeat_total:
                        intervals.extend(_expand_cycle(repeat_buffer, repeat_total))
                        repeat_buffer = []
                    repeat_total = int(repeat_in_line.group(1))
                    i += 1
                    continue
            pending_header_name = name
            pending_header_type = btype
            i += 1
            continue

        repeat_match = re.match(r"(?i)^\s*(?:main\s*set\s*)?(\d+)\s*[x\u00d7]\s*$", line)
        if not repeat_match:
            repeat_match = re.match(r"(?i)^\s*main\s*set\s+(\d+)\s*[x\u00d7]\s*$", line)
        if repeat_match:
            if repeat_buffer and repeat_total:
                for buf in repeat_buffer:
                    buf.repeat_total = repeat_total
                intervals.extend(repeat_buffer)
                repeat_buffer = []
            repeat_total = int(repeat_match.group(1))
            i += 1
            continue

        interval = _parse_interval_line(line, ftp,
                                        default_name=pending_header_name,
                                        default_type=pending_header_type)
        if interval is not None:
            pending_header_name = None
            pending_header_type = None
            if repeat_total is not None:
                repeat_buffer.append(interval)
            else:
                intervals.append(interval)
        else:
            detail_match = re.match(
                r"(?i)^\s*(\d+(?:\.\d+)?)\s*(m(?:in)?|s(?:ec)?)\s+(.*)",
                line
            )
            if detail_match:
                interval = _parse_detail_line(detail_match, ftp,
                                              pending_header_name,
                                              pending_header_type)
                if interval is not None:
                    pending_header_name = None
                    pending_header_type = None
                    if repeat_total is not None:
                        repeat_buffer.append(interval)
                    else:
                        intervals.append(interval)

        i += 1

    if repeat_buffer and repeat_total:
        intervals.extend(_expand_cycle(repeat_buffer, repeat_total))

    if not title and intervals:
        title = "Treino importado"

    return Workout(title=title, intervals=intervals)


def _expand_cycle(buffer: list[WorkoutInterval], repeat_total: int) -> list[WorkoutInterval]:
    result: list[WorkoutInterval] = []
    for i in range(repeat_total):
        for interval in buffer:
            result.append(interval.model_copy(update={
                "repeat_total": repeat_total,
                "repeat_index": i + 1,
            }))
    return result


def _match_block_header(line: str) -> tuple[str, str] | None:
    for pattern, name in [(r"(?i)^\s*warm\s*up\s*:?\s*$", "Warmup"),
                          (r"(?i)^\s*cool\s?down\s*:?\s*$", "Cooldown"),
                          (r"(?i)^\s*main\s*set\s*(?:\d+\s*[x\u00d7])?\s*$", "Main Set")]:
        if re.match(pattern, line):
            return name, "ramp" if name != "Main Set" else "steady"
    return None


def _parse_interval_line(line: str, ftp: int | None = None,
                         default_name: str | None = None,
                         default_type: str | None = None) -> WorkoutInterval | None:
    name = default_name or ""
    interval_type = default_type or "steady"
    remaining = line

    for pattern, pname, ptype in LINE_PATTERNS:
        m = re.match(pattern, line)
        if m:
            name = pname
            interval_type = ptype
            remaining = m.group(1).strip() if m.lastindex else line
            break

    dur_match = re.match(r"(?i)^\s*(\d+(?:\.\d+)?)\s*(m(?:in)?|s(?:ec)?)\s*(.*)", remaining)
    duration_seconds = 0
    if dur_match:
        val = float(dur_match.group(1))
        unit = dur_match.group(2).lower()
        if unit.startswith("m"):
            duration_seconds = int(val * 60)
        else:
            duration_seconds = int(val)
        remaining = dur_match.group(3).strip()
    else:
        dur_match = re.search(r"(?i)(\d+(?:\.\d+)?)\s*(m(?:in)?|s(?:ec)?)\b", remaining)
        if dur_match:
            val = float(dur_match.group(1))
            unit = dur_match.group(2).lower()
            if unit.startswith("m"):
                duration_seconds = int(val * 60)
            else:
                duration_seconds = int(val)

    power_min, power_max = _extract_power(remaining, ftp)
    cadence_target = _extract_cadence(remaining)

    if duration_seconds == 0 and name in ("Warmup", "Cooldown"):
        duration_seconds = 300

    if duration_seconds == 0:
        return None

    if not name:
        name = "Interval"

    return WorkoutInterval(
        name=name,
        duration_seconds=duration_seconds,
        power_min=power_min,
        power_max=power_max,
        cadence_target=cadence_target,
        type=interval_type,
    )


def _parse_detail_line(match: re.Match, ftp: int | None = None,
                       default_name: str | None = None,
                       default_type: str | None = None) -> WorkoutInterval | None:
    val = float(match.group(1))
    unit = match.group(2).lower()
    if unit.startswith("m"):
        duration_seconds = int(val * 60)
    else:
        duration_seconds = int(val)

    remaining = match.group(3).strip() if match.lastindex and match.lastindex >= 3 else ""
    name = default_name or "Interval"
    interval_type = default_type or "steady"
    power_min, power_max = _extract_power(remaining, ftp)
    cadence_target = _extract_cadence(remaining)

    if name == "Warmup" or name == "Cooldown":
        interval_type = "ramp"

    return WorkoutInterval(
        name=name,
        duration_seconds=duration_seconds,
        power_min=power_min,
        power_max=power_max,
        cadence_target=cadence_target,
        type=interval_type,
    )


def _extract_power(text: str, ftp: int | None = None) -> tuple[int | None, int | None]:
    power_min = None
    power_max = None

    watts_range = re.search(r"\((\d+)\s*[-\u2013\u2014]\s*(\d+)\s*w\)", text, re.IGNORECASE)
    if watts_range:
        power_min = int(watts_range.group(1))
        power_max = int(watts_range.group(2))
        return power_min, power_max

    watts_single = re.search(r"\((\d+)\s*w\)", text, re.IGNORECASE)
    if watts_single:
        pw = int(watts_single.group(1))
        return pw, pw

    pct_range_space = re.search(r"(?i)(\d+)%\s*[-\u2013\u2014]\s*(\d+)%", text)
    if pct_range_space and ftp:
        power_min = int(ftp * int(pct_range_space.group(1)) / 100)
        power_max = int(ftp * int(pct_range_space.group(2)) / 100)
        return power_min, power_max

    pct_range_dash = re.search(r"(?i)(\d+)\s*[-\u2013\u2014]\s*(\d+)%", text)
    if pct_range_dash and ftp:
        power_min = int(ftp * int(pct_range_dash.group(1)) / 100)
        power_max = int(ftp * int(pct_range_dash.group(2)) / 100)
        return power_min, power_max

    pct_single = re.search(r"(?i)(\d+)%\s*(?:ftp)?\b", text)
    if pct_single and ftp:
        pct = int(pct_single.group(1))
        pw = int(ftp * pct / 100)
        return pw, pw

    return None, None


def _extract_cadence(text: str) -> int | None:
    rpm_match = re.search(r"(?i)(\d+)\s*rpm", text)
    if rpm_match:
        return int(rpm_match.group(1))
    return None