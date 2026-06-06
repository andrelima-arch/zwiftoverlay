from app.intervals_icu.converter import convert_workout_doc
from app.intervals_icu.client import _extract_cycling_ftp, _extract_weight_kg
from app.workouts.parser_text import parse_workout_text


class TestIntervalsIcuProfileParser:
    def test_extracts_weight_from_icu_weight(self):
        assert _extract_weight_kg({"weight": None, "icu_weight": 85.7}) == 85.7

    def test_extracts_cycling_ftp_preferring_indoor_ftp(self):
        data = {
            "ftp": 200,
            "sportSettings": [
                {"types": ["Run"], "ftp": 300, "indoor_ftp": 301},
                {
                    "types": ["Ride", "VirtualRide"],
                    "ftp": 249,
                    "indoor_ftp": 250,
                    "mmp_model": {"ftp": 251},
                },
            ],
        }

        assert _extract_cycling_ftp(data) == 250

    def test_extracts_cycling_ftp_from_sport_setting_ftp_then_mmp_model(self):
        assert _extract_cycling_ftp(
            {"sportSettings": [{"types": ["Ride"], "ftp": 249, "mmp_model": {"ftp": 251}}]}
        ) == 249

        assert _extract_cycling_ftp(
            {"sportSettings": [{"types": ["Ride"], "mmp_model": {"ftp": 251}}]}
        ) == 251

    def test_extracts_cycling_ftp_from_legacy_top_level_field(self):
        assert _extract_cycling_ftp({"ftp": 275}) == 275


class TestIntervalsIcuConverter:
    def test_convert_simple_workout(self):
        doc = {
            "steps": [
                {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Warmup", "warmup": True, "ramp": True},
                {"duration": 600, "power": {"value": 75, "units": "%ftp"}, "text": "Endurance"},
                {"duration": 10, "power": {"value": 150, "units": "%ftp"}, "text": "Sprint", "maxeffort": True},
                {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Cooldown", "cooldown": True, "ramp": True},
            ]
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert len(w.intervals) == 4
        assert w.intervals[0].name == "Warmup"
        assert w.intervals[0].type == "ramp"
        assert w.intervals[0].duration_seconds == 300
        assert w.intervals[0].power_min == 125
        assert w.intervals[0].power_max == 125
        assert w.intervals[1].name == "Endurance"
        assert w.intervals[1].power_min == 187
        assert w.intervals[2].type == "sprint"

    def test_convert_with_reps(self):
        doc = {
            "steps": [
                {"duration": 600, "power": {"value": 75, "units": "%ftp"}, "text": "Warmup", "warmup": True},
                {"reps": 3, "steps": [
                    {"duration": 300, "power": {"value": 100, "units": "%ftp"}, "text": "Interval"},
                    {"duration": 60, "power": {"value": 50, "units": "%ftp"}, "text": "Recovery"},
                ]},
                {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Cooldown", "cooldown": True},
            ]
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert len(w.intervals) == 8
        assert w.intervals[1].name == "Interval"
        assert w.intervals[1].repeat_total == 3
        assert w.intervals[2].name == "Recovery"
        assert w.intervals[2].repeat_total == 3

    def test_convert_power_watts(self):
        doc = {
            "steps": [
                {"duration": 60, "power": {"value": 250, "units": "w"}, "text": "Test"},
            ]
        }
        w = convert_workout_doc(doc, title="Test")
        assert w.intervals[0].power_min == 250
        assert w.intervals[0].power_max == 250

    def test_convert_power_range(self):
        doc = {
            "steps": [
                {"duration": 120, "power": {"start": 50, "end": 75, "units": "%ftp"}, "text": "Ramp", "ramp": True},
            ]
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert w.intervals[0].power_min == 125
        assert w.intervals[0].power_max == 187
        assert w.intervals[0].type == "ramp"

    def test_convert_empty_doc(self):
        w = convert_workout_doc({}, title="Empty")
        assert len(w.intervals) == 0

    def test_convert_steps_as_ordered_dict(self):
        doc = {
            "steps": {
                "0": {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Warmup"},
                "1": {"duration": 600, "power": {"value": 75, "units": "%ftp"}, "text": "Endurance"},
            }
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert len(w.intervals) == 2
        assert w.intervals[0].name == "Warmup"
        assert w.intervals[0].duration_seconds == 300
        assert w.intervals[1].name == "Endurance"
        assert w.intervals[1].duration_seconds == 600

    def test_convert_steps_as_unordered_dict(self):
        doc = {
            "steps": {
                "2": {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Cooldown"},
                "0": {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Warmup"},
                "1": {"duration": 600, "power": {"value": 75, "units": "%ftp"}, "text": "Endurance"},
            }
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert len(w.intervals) == 3
        assert w.intervals[0].name == "Warmup"
        assert w.intervals[1].name == "Endurance"
        assert w.intervals[2].name == "Cooldown"

    def test_convert_with_sets_key(self):
        doc = {
            "sets": [
                {"duration": 300, "power": {"value": 50, "units": "%ftp"}, "text": "Warmup"},
                {"duration": 600, "power": {"value": 75, "units": "%ftp"}, "text": "Endurance"},
            ]
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert len(w.intervals) == 2
        assert w.intervals[0].name == "Warmup"
        assert w.intervals[1].name == "Endurance"

    def test_convert_no_steps(self):
        w = convert_workout_doc({"description": "Test"}, title="No Steps")
        assert len(w.intervals) == 0

    def test_convert_with_cadence(self):
        doc = {
            "steps": [
                {"duration": 300, "power": {"value": 75, "units": "%ftp"}, "cadence": {"value": 88}, "text": "Endurance"},
            ]
        }
        w = convert_workout_doc(doc, title="Test", ftp=250)
        assert w.intervals[0].cadence_target == 88

    def test_text_parser_and_api_produce_similar_structure(self):
        text = """Warmup
14m ramp 45-75% (112-186w) 85rpm

Main Set 6x
Endurance 11m 65-75% (161-186w) 88rpm
Sprint 10s 150% (373w) 110rpm

Cooldown
9m ramp 65-45% (161-112w) 85rpm"""
        w_text = parse_workout_text(text, ftp=250)
        assert len(w_text.intervals) == 4
        assert w_text.intervals[0].name == "Warmup"
        assert w_text.intervals[0].type == "ramp"
        assert w_text.intervals[1].repeat_total == 6
        expanded = w_text.expanded_intervals()
        assert len(expanded) == 14
