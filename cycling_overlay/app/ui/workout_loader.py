import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from app.core.events import Signal
from app.models.workout import Workout
from app.ui.i18n import normalize_language, t
from app.workouts.parser_text import parse_workout_text
from app.workouts.parser_zwo import find_zwo_files, parse_zwo_file


class WorkoutLoader(ctk.CTkFrame):
    SOURCE_KEYS = ("test", "paste", "api", "zwo")

    def __init__(self, ftp: int = 250, parent=None, config=None, language: str = "en", **kwargs):
        super().__init__(parent, **kwargs)
        self._ftp = ftp
        self._config = config
        self._language = normalize_language(language)
        self._source_key = "test"
        self._current_workout: Workout | None = None
        self._current_source: dict | None = None
        self._zwo_files: list[Path] = []
        self.workout_loaded = Signal(object)
        self.profile_synced = Signal(object)
        self.profile_sync_failed = Signal(str)

        self._source_label_widget = ctk.CTkLabel(self, text=self._text("loader.source"), font=ctk.CTkFont(weight="bold"))
        self._source_label_widget.pack(anchor="w", padx=5, pady=(5, 2))

        self._source_var = ctk.StringVar(value=self._source_label(self._source_key))
        self._source_menu = ctk.CTkOptionMenu(
            self,
            values=self._source_labels(),
            variable=self._source_var,
            command=self._on_source_changed,
        )
        self._source_menu.pack(fill="x", padx=5, pady=2)

        self._paste_frame = ctk.CTkFrame(self)

        self._paste_help_label = ctk.CTkLabel(
            self._paste_frame,
            text=self._text("loader.paste_help"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._paste_help_label.pack(anchor="w", padx=5, pady=(5, 2))

        self._text_entry = ctk.CTkTextbox(self._paste_frame, height=100)
        self._text_entry.pack(fill="both", expand=True, padx=5, pady=2)

        self._parse_button = ctk.CTkButton(
            self._paste_frame, text=self._text("loader.parse"),
            fg_color="#336699", command=self._on_parse,
        )
        self._parse_button.pack(fill="x", padx=5, pady=2)

        self._result_label = ctk.CTkLabel(self._paste_frame, text="", font=ctk.CTkFont(size=12))
        self._result_label.pack(anchor="w", padx=5, pady=(2, 5))

        self._api_frame = ctk.CTkFrame(self)

        self._api_help_label = ctk.CTkLabel(
            self._api_frame,
            text=self._text("loader.api_help"),
            font=ctk.CTkFont(weight="bold"),
        )
        self._api_help_label.pack(anchor="w", padx=5, pady=(10, 5))

        self._fetch_button = ctk.CTkButton(
            self._api_frame, text=self._text("loader.fetch"),
            fg_color="#336699", command=self._on_fetch_workouts,
        )
        self._fetch_button.pack(fill="x", padx=5, pady=5)

        self._api_status_label = ctk.CTkLabel(self._api_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._api_status_label.pack(anchor="w", padx=5, pady=2)

        self._events_frame = ctk.CTkScrollableFrame(self._api_frame, height=200)
        self._events_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self._zwo_frame = ctk.CTkFrame(self)

        self._zwo_title_label = ctk.CTkLabel(
            self._zwo_frame,
            text=self._text("loader.zwo_title"),
            font=ctk.CTkFont(weight="bold"),
        )
        self._zwo_title_label.pack(anchor="w", padx=5, pady=(10, 5))

        self._zwo_folder_label = ctk.CTkLabel(
            self._zwo_frame,
            text=self._config.last_zwo_folder if self._config and self._config.last_zwo_folder else self._text("loader.no_folder"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._zwo_folder_label.pack(anchor="w", padx=5, pady=2)

        self._zwo_select_button = ctk.CTkButton(
            self._zwo_frame,
            text=self._text("loader.select_folder"),
            fg_color="#336699",
            command=self._on_select_zwo_folder,
        )
        self._zwo_select_button.pack(fill="x", padx=5, pady=5)

        self._zwo_status_label = ctk.CTkLabel(self._zwo_frame, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._zwo_status_label.pack(anchor="w", padx=5, pady=2)

        self._zwo_list_frame = ctk.CTkScrollableFrame(self._zwo_frame, height=220)
        self._zwo_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        if self._config and self._config.last_zwo_folder:
            self._load_zwo_folder(self._config.last_zwo_folder)

        self._on_source_changed(self._source_var.get())

    def set_language(self, language: str) -> None:
        self._language = normalize_language(language)
        current_key = getattr(self, "_source_key", "test")
        self._source_var.set(self._source_label(current_key))
        self._source_menu.configure(values=self._source_labels())
        self._source_label_widget.configure(text=self._text("loader.source"))
        self._paste_help_label.configure(text=self._text("loader.paste_help"))
        self._parse_button.configure(text=self._text("loader.parse"))
        self._api_help_label.configure(text=self._text("loader.api_help"))
        self._fetch_button.configure(text=self._text("loader.fetch"))
        self._zwo_title_label.configure(text=self._text("loader.zwo_title"))
        self._zwo_select_button.configure(text=self._text("loader.select_folder"))
        if not self._config or not self._config.last_zwo_folder:
            self._zwo_folder_label.configure(text=self._text("loader.no_folder"))

    def _text(self, key: str, **params) -> str:
        return t(getattr(self, "_language", "en"), key, **params)

    def _source_label(self, key: str) -> str:
        return self._text(f"loader.source.{key}")

    def _source_labels(self) -> list[str]:
        return [self._source_label(key) for key in self.SOURCE_KEYS]

    def _source_key_from_choice(self, choice: str) -> str:
        for key in self.SOURCE_KEYS:
            if choice == self._source_label(key):
                return key
        lowered = (choice or "").lower()
        if "zwo" in lowered:
            return "zwo"
        if "buscar" in lowered or "fetch" in lowered:
            return "api"
        if "texto" in lowered or "paste" in lowered:
            return "paste"
        return "test"

    def set_ftp(self, ftp: int | None) -> None:
        self._ftp = ftp

    def rebuild_current_workout_for_ftp(self, ftp: int | None) -> Workout | None:
        self._ftp = ftp
        if not self._current_source:
            return None

        source_type = self._current_source.get("type")
        try:
            if source_type == "text":
                workout = parse_workout_text(str(self._current_source.get("text", "")), ftp=self._ftp)
            elif source_type == "intervals_doc":
                from app.intervals_icu.converter import convert_workout_doc
                workout = convert_workout_doc(self._current_source.get("workout_doc"), ftp=self._ftp)
            elif source_type == "zwo":
                workout = parse_zwo_file(Path(self._current_source.get("path", "")), ftp=self._ftp)
            else:
                return None
        except Exception:
            return None

        if not workout.intervals:
            return None
        self._current_workout = workout
        return workout

    def set_intervals_credentials(self, api_key: str, athlete_id: str) -> None:
        if self._config:
            self._config.intervals_api_key = api_key
            self._config.intervals_athlete_id = athlete_id

    def get_workout(self) -> Workout | None:
        return self._current_workout

    def _on_source_changed(self, choice: str) -> None:
        self._source_key = self._source_key_from_choice(choice)
        self._paste_frame.pack_forget()
        self._api_frame.pack_forget()
        self._zwo_frame.pack_forget()

        if self._source_key == "paste":
            self._paste_frame.pack(fill="both", expand=True, padx=5, pady=5)
        elif self._source_key == "api":
            self._api_frame.pack(fill="both", expand=True, padx=5, pady=5)
        elif self._source_key == "zwo":
            self._zwo_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _on_parse(self) -> None:
        text = self._text_entry.get("1.0", "end-1c")
        if not text.strip():
            self._result_label.configure(text=self._text("loader.empty_text"), text_color="red")
            return

        try:
            workout = parse_workout_text(text, ftp=self._ftp)
            if not workout.intervals:
                self._result_label.configure(text=self._text("loader.no_intervals"), text_color="red")
                return

            expanded = workout.expanded_intervals()
            self._current_workout = workout
            self._current_source = {"type": "text", "text": text}
            self._result_label.configure(
                text=self._text(
                    "loader.summary",
                    title=workout.title or self._text("workout.generic"),
                    blocks=len(workout.intervals),
                    intervals=len(expanded),
                ),
                text_color="green",
            )
            self.workout_loaded.emit(workout)
        except Exception as e:
            self._result_label.configure(text=self._text("loader.error", error=e), text_color="red")

    def _on_fetch_workouts(self) -> None:
        self.fetch_intervals_workouts()

    def fetch_intervals_workouts(self) -> bool:
        api_key, athlete_id = self._intervals_credentials()

        if not api_key or not athlete_id:
            self._api_status_label.configure(
                text=self._text("loader.credentials_required"),
                text_color="red",
            )
            return False

        self._fetch_button.configure(state="disabled")
        self._api_status_label.configure(text=self._text("loader.fetching"), text_color="gray")

        for widget in self._events_frame.winfo_children():
            widget.destroy()

        thread = threading.Thread(
            target=self._fetch_workouts_thread,
            args=(api_key, athlete_id),
            daemon=True,
        )
        thread.start()
        return True

    def _fetch_workouts_thread(self, api_key: str, athlete_id: str) -> None:
        try:
            from app.intervals_icu.client import IntervalsIcuClient
            client = IntervalsIcuClient(api_key=api_key, athlete_id=athlete_id)

            profile = client.get_profile()
            if profile:
                self._safe_after(lambda: self._update_profile_from_intervals(profile))
            else:
                self._safe_after(lambda: self._profile_sync_failed(self._text("loader.profile_not_found")))

            events = client.get_events(days_ahead=7, days_back=1)
            self._safe_after(lambda: self._show_events(events))
        except Exception as e:
            self._safe_after(lambda: self._show_fetch_error(str(e)))

    def _update_profile_from_intervals(self, profile) -> None:
        if profile.ftp is not None:
            self._ftp = profile.ftp
        self.profile_synced.emit(profile)
        details = []
        if profile.weight_kg is not None:
            details.append(f"{profile.weight_kg:g}kg")
        if profile.ftp is not None:
            details.append(f"{profile.ftp}w")
        self._api_status_label.configure(
            text=self._text("loader.profile_updated", details=", ".join(details))
            if details
            else self._text("loader.profile_synced_no_metrics"),
            text_color="green",
        )

    def _profile_sync_failed(self, message: str) -> None:
        self.profile_sync_failed.emit(message)
        self._api_status_label.configure(text=message, text_color="red")

    def _show_events(self, events: list) -> None:
        self._fetch_button.configure(state="normal")

        if not events:
            self._api_status_label.configure(text=self._text("loader.no_events"), text_color="gray")
            return

        self._api_status_label.configure(text=self._text("loader.events_found", count=len(events)), text_color="green")

        for event in events:
            name = event.get("name", event.get("title", self._text("loader.unnamed")))
            date = event.get("start_date_local", event.get("date", ""))
            if isinstance(date, str) and len(date) >= 10:
                date = date[:10]
            event_id = str(event.get("id", ""))
            workout_doc = event.get("workout_doc")

            display = f"{date} - {name}"
            btn = ctk.CTkButton(
                self._events_frame, text=display,
                fg_color="#4a4a4a",
                command=lambda e=event, eid=event_id, wd=workout_doc: self._on_select_event(eid, wd),
            )
            btn.pack(fill="x", padx=2, pady=1)

    def _on_select_event(self, event_id: str, workout_doc: dict | None) -> None:
        if workout_doc is None:
            api_key, athlete_id = self._intervals_credentials()
            if not api_key or not athlete_id:
                self._api_status_label.configure(
                    text=self._text("loader.credentials_required"),
                    text_color="red",
                )
                return
            self._api_status_label.configure(text=self._text("loader.loading_workout"), text_color="gray")
            thread = threading.Thread(
                target=self._fetch_and_convert_workout,
                args=(api_key, athlete_id, event_id),
                daemon=True,
            )
            thread.start()
            return

        self._apply_workout_doc(workout_doc)

    def _fetch_and_convert_workout(self, api_key: str, athlete_id: str, event_id: str) -> None:
        try:
            from app.intervals_icu.client import IntervalsIcuClient
            client = IntervalsIcuClient(api_key=api_key, athlete_id=athlete_id)
            workout_doc = client.get_workout_doc(event_id)
            self._safe_after(lambda: self._apply_workout_doc(workout_doc))
        except Exception as e:
            self._safe_after(lambda: self._api_status_label.configure(
                text=self._text("loader.error", error=e), text_color="red"
            ))

    def _apply_workout_doc(self, workout_doc: dict | None) -> None:
        if workout_doc is None:
            self._api_status_label.configure(text=self._text("loader.unable_load_workout"), text_color="red")
            return

        from app.intervals_icu.converter import convert_workout_doc
        workout = convert_workout_doc(workout_doc, ftp=self._ftp)
        if not workout.intervals:
            self._api_status_label.configure(text=self._text("loader.invalid_workout"), text_color="red")
            return

        expanded = workout.expanded_intervals()
        self._current_workout = workout
        self._current_source = {"type": "intervals_doc", "workout_doc": workout_doc}
        self._api_status_label.configure(
            text=self._text(
                "loader.summary",
                title=workout.title or self._text("workout.generic"),
                blocks=len(workout.intervals),
                intervals=len(expanded),
            ),
            text_color="green",
        )
        self.workout_loaded.emit(workout)

    def _show_fetch_error(self, error_msg: str) -> None:
        self._fetch_button.configure(state="normal")
        self._api_status_label.configure(text=self._text("loader.error", error=error_msg), text_color="red")

    def _safe_after(self, callback) -> None:
        try:
            if self.winfo_exists():
                self.after(0, callback)
        except Exception:
            pass

    def _intervals_credentials(self) -> tuple[str, str]:
        if not self._config:
            return "", ""
        return self._config.intervals_api_key.strip(), self._config.intervals_athlete_id.strip()

    def _on_select_zwo_folder(self) -> None:
        initial_dir = self._config.last_zwo_folder if self._config and self._config.last_zwo_folder else None
        options = {"parent": self}
        if initial_dir:
            options["initialdir"] = initial_dir
        folder = filedialog.askdirectory(**options)
        if not folder:
            return
        if self._config:
            self._config.last_zwo_folder = folder
        self._load_zwo_folder(folder)

    def _load_zwo_folder(self, folder: str) -> None:
        self._zwo_files = find_zwo_files(folder)
        self._zwo_folder_label.configure(text=folder)

        for widget in self._zwo_list_frame.winfo_children():
            widget.destroy()

        if not self._zwo_files:
            self._zwo_status_label.configure(text=self._text("loader.no_zwo"), text_color="gray")
            return

        self._zwo_status_label.configure(text=self._text("loader.zwo_found", count=len(self._zwo_files)), text_color="green")
        for file_path in self._zwo_files:
            btn = ctk.CTkButton(
                self._zwo_list_frame,
                text=file_path.name,
                fg_color="#4a4a4a",
                command=lambda path=file_path: self._on_select_zwo_file(path),
            )
            btn.pack(fill="x", padx=2, pady=1)

    def _on_select_zwo_file(self, path: Path) -> None:
        try:
            workout = parse_zwo_file(path, ftp=self._ftp)
            if not workout.intervals:
                self._zwo_status_label.configure(text=self._text("loader.invalid_workout"), text_color="red")
                return
            self._current_workout = workout
            self._current_source = {"type": "zwo", "path": str(path)}
            expanded = workout.expanded_intervals()
            self._zwo_status_label.configure(
                text=self._text(
                    "loader.summary",
                    title=workout.title or path.stem,
                    blocks=len(workout.intervals),
                    intervals=len(expanded),
                ),
                text_color="green",
            )
            self.workout_loaded.emit(workout)
        except Exception as e:
            self._zwo_status_label.configure(text=self._text("loader.error", error=e), text_color="red")
