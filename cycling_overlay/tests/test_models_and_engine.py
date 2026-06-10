from app.models.sensor_data import SensorData
from app.models.workout import Workout, WorkoutInterval
from app.core.workout_engine import WorkoutEngine
from app.core.state_manager import StateManager
from app.models.app_state import EngineState
from app.workouts.parser_text import parse_workout_text
from app.sensors.scanner import ScannedDevice


def _short_workout() -> Workout:
    return Workout(title="Test", intervals=[
        WorkoutInterval(name="Warmup", duration_seconds=10, power_min=100, power_max=150, type="ramp"),
        WorkoutInterval(name="Active", duration_seconds=20, power_min=150, power_max=200),
        WorkoutInterval(name="Sprint", duration_seconds=5, power_min=300, power_max=300, type="sprint"),
        WorkoutInterval(name="Cooldown", duration_seconds=10, power_min=150, power_max=100, type="ramp"),
    ])


class TestSensorData:
    def test_defaults(self):
        sd = SensorData()
        assert sd.power is None
        assert sd.cadence is None
        assert sd.heart_rate is None
        assert not sd.is_connected

    def test_stopped_power_zero(self):
        assert SensorData(power=0).is_stopped

    def test_stopped_low_hr(self):
        assert SensorData(heart_rate=35).is_stopped

    def test_stopped_zero_hr(self):
        assert SensorData(heart_rate=0).is_stopped

    def test_not_stopped(self):
        sd = SensorData(power=180, cadence=88, heart_rate=145)
        assert not sd.is_stopped
        assert sd.is_connected

    def test_is_connected_with_cadence_only(self):
        sd = SensorData(cadence=88)
        assert not sd.is_stopped
        assert sd.is_connected

    def test_stopped_threshold_hr(self):
        assert SensorData(heart_rate=39).is_stopped
        assert not SensorData(heart_rate=40).is_stopped


class TestStateManager:
    def test_weight_and_ftp_update_state(self):
        manager = StateManager()
        manager.set_weight(80)
        manager.set_ftp(300)
        manager.update_sensor_data(SensorData(power=240))

        assert manager.state.weight_kg == 80
        assert manager.state.ftp == 300
        assert manager.state.w_per_kg == 3.0

    def test_set_weight_recalculates_w_per_kg_from_current_power(self):
        manager = StateManager()
        manager.set_weight(100)
        manager.update_sensor_data(SensorData(power=250))

        manager.set_weight(50)

        assert manager.state.w_per_kg == 5.0

    def test_zero_power_remains_zero_w_per_kg_when_weight_changes(self):
        manager = StateManager()
        manager.update_sensor_data(SensorData(power=0))

        manager.set_weight(80)

        assert manager.state.w_per_kg == 0.0


class TestScanner:
    def test_detects_ftms_without_manual_type(self):
        device = ScannedDevice(
            address="AA:BB",
            name="Trainer",
            services=["00001826-0000-1000-8000-00805f9b34fb"],
        )

        assert device.detect_service_type() == "ftms"

    def test_detects_ftms_before_power_for_smart_trainer(self):
        device = ScannedDevice(
            address="AA:BB",
            name="Smart Trainer",
            services=[
                "00001818-0000-1000-8000-00805f9b34fb",
                "00001826-0000-1000-8000-00805f9b34fb",
            ],
        )

        assert device.detect_service_type() == "ftms"

    def test_unknown_sensor_remains_unknown(self):
        device = ScannedDevice(address="AA:BB", name="Unknown", services=[])

        assert device.detect_service_type() == "unknown"

    def test_qz_known_trainer_name_detects_ftms_without_uuid(self):
        device = ScannedDevice(address="AA:BB", name="KICKR CORE", services=[])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_hint == "FTMS / Wahoo KICKR QZ match"
        assert device.compatibility_profile == "wahoo_kickr"

    def test_qz_known_trainer_prioritises_ftms_over_power_uuid(self):
        device = ScannedDevice(
            address="AA:BB",
            name="ZWIFT HUB",
            services=["1818", "1826"],
        )

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_hint == "FTMS / JetBlack/Zwift Hub QZ match"
        assert device.compatibility_profile == "jetblack"

    def test_thinkrider_name_detects_ftms_with_qz_profile(self):
        device = ScannedDevice(address="AA:BB", name="THINK X2MAX", services=[])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_hint == "FTMS / ThinkRider QZ match"
        assert device.compatibility_profile == "think_x"

    def test_thinkrider_dash_name_detects_ftms_with_qz_profile(self):
        device = ScannedDevice(address="AA:BB", name="THINK-X2", services=["1818"])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_profile == "think_x"

    def test_x2max_name_detects_thinkrider_profile(self):
        device = ScannedDevice(address="AA:BB", name="X2MAX", services=["1818"])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_profile == "think_x"

    def test_qz_known_elite_name_detects_profile(self):
        device = ScannedDevice(address="AA:BB", name="DIRETO XR", services=[])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_profile == "elite"

    def test_qz_known_tacx_neo_name_detects_profile(self):
        device = ScannedDevice(address="AA:BB", name="TACX NEO 2T", services=["1818"])

        assert device.detect_service_type() == "ftms"
        assert device.compatibility_profile == "tacxneo2_like"

    def test_hr_power_and_csc_standard_profiles(self):
        hr = ScannedDevice(address="AA:BB", name="Garmin HR", services=["180d"])
        power = ScannedDevice(address="CC:DD", name="Power Meter", services=["1818"])
        csc = ScannedDevice(address="EE:FF", name="Cadence Sensor", services=["1816"])

        assert hr.detect_service_type() == "hr"
        assert hr.compatibility_profile == "heart_rate"
        assert power.detect_service_type() == "power"
        assert power.compatibility_profile == "cycling_power"
        assert csc.detect_service_type() == "csc"
        assert csc.compatibility_profile == "csc"


class TestWorkoutInterval:
    def test_target_display_range(self):
        i = WorkoutInterval(name="E", duration_seconds=60, power_min=161, power_max=186)
        assert i.target_display == "161-186w"

    def test_target_display_single(self):
        i = WorkoutInterval(name="S", duration_seconds=10, power_min=373, power_max=373)
        assert i.target_display == "373w"

    def test_target_display_none(self):
        i = WorkoutInterval(name="R", duration_seconds=60)
        assert i.target_display == "---w"

    def test_ramp_power_at_elapsed(self):
        i = WorkoutInterval(name="Ramp", duration_seconds=100, power_min=100, power_max=200, type="ramp")
        assert i.power_at_elapsed(0) == 100
        assert i.power_at_elapsed(50) == 150
        assert i.power_at_elapsed(100) == 200

    def test_ramp_power_at_elapsed_none(self):
        i = WorkoutInterval(name="Ramp", duration_seconds=100, type="ramp")
        assert i.power_at_elapsed(50) is None

    def test_steady_power_at_elapsed(self):
        i = WorkoutInterval(name="E", duration_seconds=60, power_min=161, power_max=186)
        assert i.power_at_elapsed(30) == 186

    def test_progress_percent_property(self):
        i = WorkoutInterval(name="E", duration_seconds=60, power_min=161, power_max=186)
        assert i.progress_percent == 0.0


class TestWorkoutExpansion:
    def test_expanded_returns_intervals_as_is(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="E", duration_seconds=60, power_min=161, power_max=186, repeat_total=3, repeat_index=1),
        ])
        expanded = w.expanded_intervals()
        assert len(expanded) == 1
        assert expanded[0].repeat_index == 1
        assert expanded[0].repeat_total == 3

    def test_no_repeat(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="W", duration_seconds=840, power_min=112, power_max=186),
        ])
        expanded = w.expanded_intervals()
        assert len(expanded) == 1
        assert expanded[0].repeat_index is None

    def test_multiple_intervals_preserved(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="W", duration_seconds=120),
            WorkoutInterval(name="E", duration_seconds=60, repeat_total=2, repeat_index=1),
            WorkoutInterval(name="C", duration_seconds=120),
        ])
        expanded = w.expanded_intervals()
        assert len(expanded) == 3


class TestWorkoutEngine:
    def test_start(self):
        engine = WorkoutEngine()
        engine.load_workout(_short_workout())
        engine.start()
        assert engine.state == EngineState.RUNNING
        assert engine.current_interval is not None
        assert engine.current_interval.name == "Warmup"

    def test_ticks_advance(self):
        engine = WorkoutEngine()
        engine.load_workout(_short_workout())
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(5):
            engine._on_tick()
        assert engine._elapsed_in_interval == 5

    def test_advance_to_next_interval(self):
        engine = WorkoutEngine()
        engine.load_workout(_short_workout())
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(11):
            engine._on_tick()
        assert engine.current_interval.name == "Active"

    def test_pause_under_80_percent(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="Long", duration_seconds=100, power_min=150, power_max=200),
        ])
        engine = WorkoutEngine()
        engine.load_workout(w)
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(3):
            engine._on_tick()
        assert engine.current_progress < 0.80
        engine.update_sensor(SensorData(power=0))
        for _ in range(61):
            engine._on_tick()
        assert engine.state == EngineState.PAUSED

    def test_resume_from_pause(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="Long", duration_seconds=100, power_min=150, power_max=200),
        ])
        engine = WorkoutEngine()
        engine.load_workout(w)
        engine.start()
        engine.update_sensor(SensorData(power=0))
        for _ in range(61):
            engine._on_tick()
        assert engine.state == EngineState.PAUSED
        engine.update_sensor(SensorData(power=180))
        engine._on_tick()
        assert engine.state == EngineState.RUNNING

    def test_between_intervals_over_80_percent_user_stopped(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="Short", duration_seconds=10, power_min=150, power_max=200),
            WorkoutInterval(name="Next", duration_seconds=10, power_min=200, power_max=250),
        ])
        engine = WorkoutEngine()
        engine.load_workout(w)
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(9):
            engine._on_tick()
        assert engine.current_progress >= 0.80
        engine.update_sensor(SensorData(power=0))
        for _ in range(70):
            engine._on_tick()
        assert engine.state == EngineState.BETWEEN_INTERVALS

    def test_between_intervals_advances_when_user_pedals(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="Short", duration_seconds=10, power_min=150, power_max=200),
            WorkoutInterval(name="Next", duration_seconds=10, power_min=200, power_max=250),
        ])
        engine = WorkoutEngine()
        engine.load_workout(w)
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(9):
            engine._on_tick()
        engine.update_sensor(SensorData(power=0))
        for _ in range(70):
            engine._on_tick()
        assert engine.state == EngineState.BETWEEN_INTERVALS
        engine.update_sensor(SensorData(power=200))
        engine._on_tick()
        assert engine.state == EngineState.RUNNING
        assert engine.current_interval.name == "Next"

    def test_finishes_last_interval(self):
        w = Workout(title="T", intervals=[
            WorkoutInterval(name="Last", duration_seconds=5, power_min=150, power_max=200),
        ])
        engine = WorkoutEngine()
        engine.load_workout(w)
        engine.start()
        engine.update_sensor(SensorData(power=180))
        for _ in range(6):
            engine._on_tick()
        assert engine.state == EngineState.FINISHED

    def test_replace_workout_preserves_index_elapsed_and_reemits_interval(self):
        engine = WorkoutEngine()
        engine.load_workout(_short_workout())
        engine.start()
        emitted = []
        engine.interval_changed.connect(lambda interval, elapsed, progress: emitted.append((interval, elapsed, progress)))
        engine._current_index = 1
        engine._elapsed_in_interval = 7

        updated = Workout(title="Updated", intervals=[
            WorkoutInterval(name="Warmup", duration_seconds=10, power_min=120, power_max=160, type="ramp"),
            WorkoutInterval(name="Active", duration_seconds=20, power_min=200, power_max=240),
        ])

        engine.replace_workout_preserving_progress(updated)

        assert engine.current_interval.name == "Active"
        assert engine.current_interval.power_max == 240
        assert engine._elapsed_in_interval == 7
        assert emitted[-1][0].power_max == 240


class TestParserText:
    def test_parse_simple_interval(self):
        text = "Endurance 11m 65-75% (161-186w) 88rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.name == "Endurance"
        assert i.duration_seconds == 660
        assert i.power_min == 161
        assert i.power_max == 186
        assert i.cadence_target == 88

    def test_parse_warmup_ramp(self):
        text = "Warmup\n14m ramp 45-75% (112-186w) 85rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.name == "Warmup"
        assert i.type == "ramp"
        assert i.duration_seconds == 840

    def test_parse_cooldown(self):
        text = "Cooldown\n9m ramp 65-45% (161-112w) 85rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.name == "Cooldown"
        assert i.type == "ramp"

    def test_parse_seconds(self):
        text = "Sprint 10s 150% (373w) 110rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.name == "Sprint"
        assert i.duration_seconds == 10
        assert i.type == "sprint"

    def test_parse_with_ftp_conversion(self):
        text = "Endurance 11m 65-75% 88rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.power_min == 162
        assert i.power_max == 187

    def test_parse_without_ftp(self):
        text = "Endurance 11m 65-75% 88rpm"
        w = parse_workout_text(text, ftp=None)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.power_min is None
        assert i.power_max is None

    def test_parse_repeat_block(self):
        text = """Main Set 6x
Endurance 11m 65-75% (161-186w) 88rpm
Sprint 10s 150% (373w) 110rpm

Cooldown
9m ramp 65-45% (161-112w) 85rpm"""
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 13
        assert w.intervals[0].repeat_total == 6
        assert w.intervals[0].repeat_index == 1
        assert w.intervals[1].repeat_total == 6
        assert w.intervals[1].repeat_index == 1

    def test_parse_full_workout(self):
        text = """Warmup
Ol\u00e1 Andre! Endurance e sprints pela frente. 14m ramp 45-75% (112-186w) 85rpm

Main Set 6x
Endurance 11m 65-75% (161-186w) 88rpm
Sprint 10s 150% (373w) 110rpm

Cooldown
Bom trabalho Andre aproveite o relaxamento. 9m ramp 65-45% (161-112w) 85rpm"""
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) >= 3
        expanded = w.expanded_intervals()
        assert len(expanded) >= 13

    def test_parse_empty_input(self):
        w = parse_workout_text("", ftp=250)
        assert len(w.intervals) == 0

    def test_parse_single_power_watts(self):
        text = "Sprint 10s (373w) 110rpm"
        w = parse_workout_text(text, ftp=250)
        assert len(w.intervals) == 1
        i = w.intervals[0]
        assert i.power_min == 373
        assert i.power_max == 373
