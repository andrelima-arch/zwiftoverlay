from pathlib import Path
from types import SimpleNamespace

from app.core.events import Signal
from app.ui.workout_loader import WorkoutLoader


def test_workout_loader_reads_intervals_credentials_from_config():
    loader = object.__new__(WorkoutLoader)
    loader._config = SimpleNamespace(
        intervals_api_key=" secret ",
        intervals_athlete_id=" athlete ",
    )

    assert WorkoutLoader._intervals_credentials(loader) == ("secret", "athlete")


def test_workout_loader_set_intervals_credentials_updates_config_only():
    config = SimpleNamespace(intervals_api_key="", intervals_athlete_id="")
    loader = object.__new__(WorkoutLoader)
    loader._config = config

    WorkoutLoader.set_intervals_credentials(loader, "api-key", "athlete-id")

    assert config.intervals_api_key == "api-key"
    assert config.intervals_athlete_id == "athlete-id"


def test_workout_loader_fetch_intervals_workouts_uses_config_credentials(monkeypatch):
    config = SimpleNamespace(intervals_api_key="api-key", intervals_athlete_id="athlete-id")
    loader = object.__new__(WorkoutLoader)
    loader._config = config
    loader._api_status_label = SimpleNamespace(configure=lambda **_kwargs: None)
    loader._list_frame = SimpleNamespace(winfo_children=lambda: [])
    started = []

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started.append((self.target, self.args, self.daemon))

    monkeypatch.setattr("app.ui.workout_loader.threading.Thread", FakeThread)

    assert WorkoutLoader.fetch_intervals_workouts(loader) is True
    target, args, daemon = started[0]
    assert target.__func__ is WorkoutLoader._fetch_workouts_thread
    assert args == ("api-key", "athlete-id")
    assert daemon is True


def test_workout_loader_fetch_intervals_workouts_requires_credentials():
    config = SimpleNamespace(intervals_api_key="", intervals_athlete_id="")
    loader = object.__new__(WorkoutLoader)
    loader._config = config
    statuses = []
    loader._api_status_label = SimpleNamespace(configure=lambda **kwargs: statuses.append(kwargs))

    assert WorkoutLoader.fetch_intervals_workouts(loader) is False
    assert statuses[-1]["text"].startswith("Enter API Key")


def test_workout_loader_translates_source_options_and_messages():
    loader = object.__new__(WorkoutLoader)
    loader._language = "en"

    assert WorkoutLoader._source_label(loader, "api") == "Fetch from intervals.icu"
    assert WorkoutLoader._source_key_from_choice(loader, "Paste intervals.icu text") == "paste"

    loader._language = "pt"

    assert WorkoutLoader._source_label(loader, "api") == "Buscar do intervals.icu"
    assert WorkoutLoader._source_key_from_choice(loader, "Colar texto do intervals.icu") == "paste"


def test_workout_loader_profile_update_accepts_zero_values():
    loader = object.__new__(WorkoutLoader)
    loader._ftp = 250
    loader.profile_synced = Signal(object)
    loader._api_status_label = SimpleNamespace(configure=lambda **_kwargs: None)
    emitted = []
    loader.profile_synced.connect(lambda profile: emitted.append(profile))

    profile = SimpleNamespace(weight_kg=0.0, ftp=0)

    WorkoutLoader._update_profile_from_intervals(loader, profile)

    assert loader._ftp == 0
    assert emitted == [profile]


def test_workout_loader_rebuilds_current_text_workout_for_new_ftp():
    loader = object.__new__(WorkoutLoader)
    loader._ftp = 250
    loader._current_workout = None
    loader._current_source = {"type": "text", "text": "Endurance 10m 50% ftp"}

    workout = WorkoutLoader.rebuild_current_workout_for_ftp(loader, 300)

    assert workout is not None
    assert workout.intervals[0].power_min == 150
    assert loader._current_workout == workout


def test_workout_loader_intervals_buttons_align_text_left(monkeypatch):
    created = []

    class FakeButton:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            created.append(self)

        def pack(self, **_kwargs):
            pass

    loader = object.__new__(WorkoutLoader)
    loader._language = "en"
    loader._api_status_label = SimpleNamespace(configure=lambda **_kwargs: None)
    loader._list_frame = SimpleNamespace(winfo_children=lambda: [])
    monkeypatch.setattr("app.ui.workout_loader.ctk.CTkButton", FakeButton)

    WorkoutLoader._show_events(
        loader,
        [
            {
                "id": "1",
                "name": "Endurance",
                "start_date_local": "2026-06-05T10:00:00",
                "workout_doc": {},
            }
        ],
    )

    assert created[0].kwargs["anchor"] == "w"


def test_workout_loader_zwo_buttons_align_text_left(monkeypatch):
    created = []

    class FakeButton:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            created.append(self)

        def pack(self, **_kwargs):
            pass

    loader = object.__new__(WorkoutLoader)
    loader._language = "en"
    loader._zwo_files = []
    loader._zwo_folder_label = SimpleNamespace(configure=lambda **_kwargs: None)
    loader._zwo_status_label = SimpleNamespace(configure=lambda **_kwargs: None)
    loader._list_frame = SimpleNamespace(winfo_children=lambda: [])
    monkeypatch.setattr("app.ui.workout_loader.ctk.CTkButton", FakeButton)
    monkeypatch.setattr(
        "app.ui.workout_loader.find_zwo_files",
        lambda _folder: [Path("/tmp/base.zwo")],
    )

    WorkoutLoader._load_zwo_folder(loader, "/tmp")

    assert created[0].kwargs["anchor"] == "w"
