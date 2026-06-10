from app.workouts.parser_zwo import find_zwo_files, parse_zwo_file


def test_parse_zwo_common_blocks(tmp_path):
    path = tmp_path / "test.zwo"
    path.write_text(
        """<workout_file>
  <name>ZWO Test</name>
  <workout>
    <Warmup Duration="300" PowerLow="0.50" PowerHigh="0.75" Cadence="85" />
    <SteadyState Duration="600" Power="0.80" Cadence="90">
      <textevent timeoffset="0" message="Long aerobic text" />
    </SteadyState>
    <IntervalsT Repeat="3" OnDuration="60" OffDuration="30" OnPower="1.20" OffPower="0.55" Cadence="100" CadenceRest="80" />
    <Cooldown Duration="240" PowerLow="0.70" PowerHigh="0.45" />
    <FreeRide Duration="120" />
  </workout>
</workout_file>""",
        encoding="utf-8",
    )

    workout = parse_zwo_file(path, ftp=250)

    assert workout.title == "ZWO Test"
    assert len(workout.intervals) == 10
    assert workout.intervals[0].name == "Warmup"
    assert workout.intervals[0].type == "ramp"
    assert workout.intervals[0].power_min == 125
    assert workout.intervals[0].power_max == 187
    assert workout.intervals[1].name == "Long aerobic text"
    assert workout.intervals[1].power_min == 200
    assert workout.intervals[2].repeat_total == 3
    assert workout.intervals[2].repeat_index == 1
    assert workout.intervals[2].power_max == 300
    assert workout.intervals[3].name == "Recovery"
    assert workout.intervals[3].type == "recovery"
    assert workout.intervals[3].repeat_index == 1
    assert workout.intervals[8].name == "Cooldown"
    assert workout.intervals[9].name == "Free Ride"
    assert workout.intervals[9].power_min is None


def test_find_zwo_files_sorted_recursively(tmp_path):
    (tmp_path / "b.zwo").write_text("<workout_file />", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "a.zwo").write_text("<workout_file />", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("", encoding="utf-8")

    files = find_zwo_files(tmp_path)

    assert [path.name for path in files] == ["a.zwo", "b.zwo"]
