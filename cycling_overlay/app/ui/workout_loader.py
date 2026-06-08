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
    SOURCE_KEYS = ("api", "paste", "zwo")

    def __init__(self, ftp: int = 250, parent=None, config=None, language: str = "en", **kwargs):
        super().__init__(parent, **kwargs)
        self._ftp = ftp
        self._config = config
        self._language = normalize_language(language)
        self._source_key = "api"
        self._current_workout: Workout | None = None
        self._current_source: dict | None = None
        self._zwo_files: list[Path] = []
        self._intervals_visible = False
        self.workout_loaded = Signal(object)
        self.profile_synced = Signal(object)
        self.profile_sync_failed = Signal(str)
        self.start_requested = Signal()

        self._all_api_events: list[dict] = []
        self._all_zwo_files: list[Path] = []

        self._source_bar = ctk.CTkFrame(self, fg_color="transparent")
        self._source_bar.pack(fill="x", padx=5, pady=(5, 0))

        self._source_label_widget = ctk.CTkLabel(
            self._source_bar, text=self._text("loader.source"),
            font=ctk.CTkFont(weight="bold"),
        )
        self._source_label_widget.pack(side="left", padx=(5, 6))

        self._source_var = ctk.StringVar(value=self._source_label(self._source_key))
        self._source_menu = ctk.CTkOptionMenu(
            self._source_bar,
            values=self._source_labels(),
            variable=self._source_var,
            command=self._on_source_changed,
            width=220,
        )
        self._source_menu.pack(side="left")

        self._controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._controls_frame.pack(fill="x", padx=5, pady=(3, 0))

        self._paste_controls = ctk.CTkFrame(self._controls_frame)
        self._paste_help_label = ctk.CTkLabel(
            self._paste_controls,
            text=self._text("loader.paste_help"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._paste_help_label.pack(anchor="w", padx=5, pady=(2, 0))
        self._text_entry = ctk.CTkTextbox(self._paste_controls, height=80)
        self._text_entry.pack(fill="x", padx=5, pady=2)
        self._parse_button = ctk.CTkButton(
            self._paste_controls, text=self._text("loader.parse"),
            fg_color="#336699", command=self._on_parse,
        )
        self._parse_button.pack(fill="x", padx=5, pady=2)

        self._api_controls = ctk.CTkFrame(self._controls_frame)
        self._api_help_label = ctk.CTkLabel(
            self._api_controls,
            text=self._text("loader.api_help"),
            font=ctk.CTkFont(weight="bold"),
        )
        self._api_help_label.pack(anchor="w", padx=5, pady=(2, 3))
        self._api_status_label = ctk.CTkLabel(
            self._api_controls, text="",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._api_status_label.pack(anchor="w", padx=5, pady=(0, 3))

        self._zwo_controls = ctk.CTkFrame(self._controls_frame)
        self._zwo_title_label = ctk.CTkLabel(
            self._zwo_controls,
            text=self._text("loader.zwo_title"),
            font=ctk.CTkFont(weight="bold"),
        )
        self._zwo_title_label.pack(anchor="w", padx=5, pady=(2, 3))
        self._zwo_folder_label = ctk.CTkLabel(
            self._zwo_controls,
            text=self._config.last_zwo_folder if self._config and self._config.last_zwo_folder else self._text("loader.no_folder"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._zwo_folder_label.pack(anchor="w", padx=5, pady=2)
        btn_row2 = ctk.CTkFrame(self._zwo_controls, fg_color="transparent")
        btn_row2.pack(fill="x", padx=5, pady=2)
        self._zwo_select_button = ctk.CTkButton(
            btn_row2,
            text=self._text("loader.select_folder"),
            fg_color="#336699",
            command=self._on_select_zwo_folder,
        )
        self._zwo_select_button.pack(side="left")
        self._zwo_status_label = ctk.CTkLabel(
            self._zwo_controls, text="",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._zwo_status_label.pack(anchor="w", padx=5, pady=(0, 3))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_list())
        self._search_entry = ctk.CTkEntry(
            self,
            textvariable=self._search_var,
            placeholder_text=self._text("loader.search"),
            font=ctk.CTkFont(size=12),
        )
        self._search_entry.pack(fill="x", padx=5, pady=(3, 0))

        self._list_frame = ctk.CTkScrollableFrame(self, height=280)
        self._list_frame.pack(fill="both", expand=True, padx=5, pady=3)

        self._back_button = ctk.CTkButton(
            self,
            text="\u2190 " + self._text("loader.back"),
            fg_color="#4a4a4a",
            command=self._hide_intervals,
            height=28,
        )

        self._start_workout_btn = ctk.CTkButton(
            self,
            text="\u25b6 " + self._text("workout.start"),
            fg_color="#336699",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_start_clicked,
            height=32,
        )

        self._intervals_header = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(weight="bold", size=12),
        )

        self._intervals_list_frame = ctk.CTkScrollableFrame(self, height=260)

        if self._config and self._config.last_zwo_folder:
            self._load_zwo_folder(self._config.last_zwo_folder)

        self._on_source_changed(self._source_var.get())

    def set_language(self, language: str) -> None:
        self._language = normalize_language(language)
        current_key = getattr(self, "_source_key", "api")
        self._source_var.set(self._source_label(current_key))
        self._source_menu.configure(values=self._source_labels())
        self._source_label_widget.configure(text=self._text("loader.source"))
        self._paste_help_label.configure(text=self._text("loader.paste_help"))
        self._parse_button.configure(text=self._text("loader.parse"))
        self._api_help_label.configure(text=self._text("loader.api_help"))
        self._zwo_title_label.configure(text=self._text("loader.zwo_title"))
        self._zwo_select_button.configure(text=self._text("loader.select_folder"))
        self._search_entry.configure(placeholder_text=self._text("loader.search"))
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
        return "api"

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
        self._paste_controls.pack_forget()
        self._api_controls.pack_forget()
        self._zwo_controls.pack_forget()
        self._hide_intervals()
        self._clear_list()

        if self._source_key in ("api", "zwo", "paste"):
            self._search_entry.pack(fill="x", padx=5, pady=(3, 0))
            self._list_frame.pack(fill="both", expand=True, padx=5, pady=3)
        else:
            self._search_entry.pack_forget()
            self._list_frame.pack_forget()

        if self._source_key == "paste":
            self._paste_controls.pack(fill="x")
        elif self._source_key == "api":
            self._api_controls.pack(fill="x")
            self.after(200, self._try_auto_fetch_api)
        elif self._source_key == "zwo":
            self._zwo_controls.pack(fill="x")

    def _try_auto_fetch_api(self) -> None:
        if not self.winfo_exists():
            return
        self.fetch_intervals_workouts()

    def _clear_list(self) -> None:
        for widget in self._list_frame.winfo_children():
            widget.destroy()

    def _filter_list(self) -> None:
        query = self._search_var.get().strip().lower()
        if self._source_key == "api":
            events = self._all_api_events
            if query:
                events = [e for e in events if query in (e.get("name", "") + e.get("title", "")).lower()]
            self._render_api_event_buttons(events)
        elif self._source_key == "zwo":
            files = self._all_zwo_files
            if query:
                files = [f for f in files if query in f.name.lower()]
            self._render_zwo_file_buttons(files)

    def _on_parse(self) -> None:
        text = self._text_entry.get("1.0", "end-1c")
        if not text.strip():
            return

        try:
            workout = parse_workout_text(text, ftp=self._ftp)
            if not workout.intervals:
                return

            self._current_workout = workout
            self._current_source = {"type": "text", "text": text}
            self._show_intervals(workout)
            self.workout_loaded.emit(workout)
        except Exception:
            pass

    def fetch_intervals_workouts(self) -> bool:
        api_key, athlete_id = self._intervals_credentials()

        if not api_key or not athlete_id:
            self._api_status_label.configure(
                text=self._text("loader.credentials_required"),
                text_color="red",
            )
            return False

        self._api_status_label.configure(text=self._text("loader.fetching"), text_color="gray")
        self._clear_list()

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
        except Exception as ex:
            self._safe_after(lambda msg=str(ex): self._show_fetch_error(msg))

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
        self._all_api_events = events

        if not events:
            self._api_status_label.configure(text=self._text("loader.no_events"), text_color="gray")
            return

        self._api_status_label.configure(text=self._text("loader.events_found", count=len(events)), text_color="green")
        self._render_api_event_buttons(events)

    def _render_api_event_buttons(self, events: list) -> None:
        self._clear_list()
        for event in events:
            name = event.get("name", event.get("title", self._text("loader.unnamed")))
            date = event.get("start_date_local", event.get("date", ""))
            if isinstance(date, str) and len(date) >= 10:
                date = date[:10]
            event_id = str(event.get("id", ""))
            workout_doc = event.get("workout_doc")

            display = f"{date} - {name}"
            btn = ctk.CTkButton(
                self._list_frame, text=display,
                anchor="w",
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
        except Exception as ex:
            self._safe_after(lambda msg=str(ex): self._api_status_label.configure(
                text=self._text("loader.error", error=msg), text_color="red"
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

        self._current_workout = workout
        self._current_source = {"type": "intervals_doc", "workout_doc": workout_doc}
        self._show_intervals(workout)
        self.workout_loaded.emit(workout)

    def _show_fetch_error(self, error_msg: str) -> None:
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
        self._all_zwo_files = list(self._zwo_files)
        self._zwo_folder_label.configure(text=folder)

        if not self._zwo_files:
            self._zwo_status_label.configure(text=self._text("loader.no_zwo"), text_color="gray")
            return

        self._zwo_status_label.configure(text=self._text("loader.zwo_found", count=len(self._zwo_files)), text_color="green")
        self._render_zwo_file_buttons(self._zwo_files)

    def _render_zwo_file_buttons(self, files: list[Path]) -> None:
        self._clear_list()
        for file_path in files:
            btn = ctk.CTkButton(
                self._list_frame,
                text=file_path.name,
                anchor="w",
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
            self._show_intervals(workout)
            self.workout_loaded.emit(workout)
        except Exception as e:
            self._zwo_status_label.configure(text=self._text("loader.error", error=e), text_color="red")

    def _show_intervals(self, workout: Workout) -> None:
        self._intervals_visible = True
        self._search_entry.pack_forget()
        self._list_frame.pack_forget()
        self._controls_frame.pack_forget()

        for widget in self._intervals_list_frame.winfo_children():
            widget.destroy()

        intervals = workout.expanded_intervals()
        header_text = self._text(
            "loader.summary",
            title=workout.title or self._text("workout.generic"),
            blocks=len(workout.intervals),
            intervals=len(intervals),
        )
        self._intervals_header.configure(text=header_text)

        type_colors = {"ramp": "#00cc66", "steady": "#3399ff", "sprint": "#ff4444", "recovery": "#888888"}

        for i, interval in enumerate(intervals):
            color = type_colors.get(interval.type, "#3399ff")
            dur = interval.duration_seconds
            dur_str = f"{dur // 60}:{dur % 60:02d}" if dur >= 60 else f"0:{dur:02d}"
            power = interval.target_display
            cad = f"{interval.cadence_target}rpm" if interval.cadence_target else "---"
            line = ctk.CTkLabel(
                self._intervals_list_frame,
                text=f"{i+1:2d}  {interval.name[:22]:<22}  {dur_str}  {power:>10}  {cad:>6}",
                font=ctk.CTkFont(size=11, family="Consolas"),
                text_color=color,
                anchor="w",
            )
            line.pack(fill="x", padx=4, pady=0)

        self._intervals_header.pack(fill="x", padx=5, pady=(5, 2))
        self._intervals_list_frame.pack(fill="both", expand=False, padx=4, pady=2)
        self._back_button.pack(fill="x", padx=5, pady=(4, 2))
        self._start_workout_btn.pack(fill="x", padx=5, pady=(4, 5))

    def _on_start_clicked(self) -> None:
        self.start_requested.emit()

    def _hide_intervals(self) -> None:
        if not self._intervals_visible:
            return
        self._intervals_visible = False
        self._back_button.pack_forget()
        self._start_workout_btn.pack_forget()
        self._intervals_header.pack_forget()
        self._intervals_list_frame.pack_forget()

        self._controls_frame.pack(fill="x", padx=5, pady=(3, 0))
        if self._source_key in ("api", "zwo", "paste"):
            self._search_entry.pack(fill="x", padx=5, pady=(3, 0))
        self._list_frame.pack(fill="both", expand=True, padx=5, pady=3)
