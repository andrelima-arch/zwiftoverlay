import tkinter as tk
import tkinter.font as tkfont

from app.ui.i18n import normalize_language, t


class MarqueeLabel(tk.Canvas):
    def __init__(self, parent, text="", fg="white", bg="#000000", font=("Consolas", 11, "bold"), **kwargs):
        super().__init__(parent, bg=bg, highlightthickness=0, height=22, **kwargs)
        self._text = text
        self._fg = fg
        self._font = tkfont.Font(font=font)
        self._x = 0
        self._after_id = None
        self._item = self.create_text(0, 11, text=text, fill=fg, font=self._font, anchor="w")
        self.bind("<Configure>", lambda _: self._reset_position())
        self._schedule_tick()

    def set_text(self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        self.itemconfigure(self._item, text=text)
        self._reset_position()

    def _reset_position(self) -> None:
        width = self.winfo_width()
        text_width = self._font.measure(self._text)
        self._x = max((width - text_width) // 2, 0)
        self.coords(self._item, self._x, 11)

    def _tick(self) -> None:
        width = self.winfo_width()
        text_width = self._font.measure(self._text)
        if self._text and text_width > width:
            self._x -= 2
            if self._x < -text_width:
                self._x = width
            self.coords(self._item, self._x, 11)
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        self._after_id = self.after(80, self._tick)

    def destroy(self) -> None:
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        super().destroy()


class OverlayWindow(tk.Toplevel):
    def __init__(self, language: str = "en") -> None:
        super().__init__()
        self._language = normalize_language(language)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", "")
        self.configure(bg="black")

        self._drag_x = None
        self._drag_y = None

        self._line1 = tk.Label(
            self, text="---w / ---rpm / ---bpm",
            fg="white", bg="#000000",
            font=("Consolas", 16, "bold"),
            anchor="center",
        )
        self._line1.pack(fill="x", padx=10, pady=(8, 2))

        self._line2 = tk.Label(
            self, text="---w / --- w/kg",
            fg="#00ff88", bg="#000000",
            font=("Consolas", 16, "bold"),
            anchor="center",
        )
        self._line2.pack(fill="x", padx=10, pady=2)

        self._line3 = MarqueeLabel(
            self,
            text="",
            fg="#ffaa00", bg="#000000",
            font=("Consolas", 11, "bold"),
        )
        self._line3.pack(fill="x", padx=10, pady=(2, 8))

        self.geometry("+{}+{}".format(
            self.winfo_screenwidth() - 320,
            20,
        ))
        self.update_idletasks()
        w = self._line1.winfo_reqwidth() + 24
        h = self._line1.winfo_reqheight() + self._line2.winfo_reqheight() + self._line3.winfo_reqheight() + 20
        self.geometry(f"{w}x{h}+{self.winfo_screenwidth() - w - 20}+20")

        self._line1.bind("<ButtonPress-1>", self._on_press)
        self._line1.bind("<B1-Motion>", self._on_drag)
        self._line2.bind("<ButtonPress-1>", self._on_press)
        self._line2.bind("<B1-Motion>", self._on_drag)
        self._line3.bind("<ButtonPress-1>", self._on_press)
        self._line3.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)

    def set_language(self, language: str) -> None:
        self._language = normalize_language(language)

    def _text(self, key: str, **params) -> str:
        return t(getattr(self, "_language", "en"), key, **params)

    def _on_press(self, event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event) -> None:
        if self._drag_x is not None and self._drag_y is not None:
            x = self.winfo_x() + event.x - self._drag_x
            y = self.winfo_y() + event.y - self._drag_y
            self.geometry(f"+{x}+{y}")

    def update_state(self, state) -> None:
        from app.models.app_state import EngineState
        sd = state.sensor_data

        if state.engine_state == EngineState.PAUSED:
            self._line1.config(text="---w / ---rpm / ---bpm")
            self._line2.config(text=self._text("overlay.paused"), fg="#ffaa00")
            if state.current_interval:
                pct = int(state.interval_progress_percent * 100)
                self._line3.set_text(self._text("overlay.interval_progress", pct=pct))
            return

        if state.engine_state == EngineState.BETWEEN_INTERVALS:
            self._line1.config(text="---w / ---rpm / ---bpm")
            next_name = ""
            if state.current_interval:
                next_name = state.current_interval.name
                ri = state.current_interval.repeat_index
                rt = state.current_interval.repeat_total
                if ri and rt:
                    next_name = f"{next_name} {ri}/{rt}"
            self._line2.config(text=self._text("overlay.next", name=next_name), fg="#ffaa00")
            self._line3.set_text(self._text("overlay.pedal_start"))
            return

        power_str = f"{sd.power}w" if sd.power is not None else "---w"
        cadence_str = f"{sd.cadence}rpm" if sd.cadence is not None else "---rpm"
        hr_str = f"{sd.heart_rate}bpm" if sd.heart_rate is not None else "---bpm"
        line1_text = f"{power_str} / {cadence_str} / {hr_str}"

        remaining = state.interval_remaining_seconds
        if state.engine_state == EngineState.RUNNING and 1 <= remaining <= 5:
            line1_text += f" | 0:0{remaining}"
            self._line1.config(text=line1_text, fg="#ffaa00")
        else:
            self._line1.config(text=line1_text, fg="white")

        if state.current_interval and state.current_target_power is not None:
            target = state.current_interval.target_display
            wkg_str = f"{state.w_per_kg} w/kg" if state.w_per_kg is not None else "--- w/kg"
            self._line2.config(text=f"{target} / {wkg_str}", fg="#00ff88")
        elif state.current_interval is None and state.engine_state == EngineState.FINISHED:
            self._line2.config(text=self._text("overlay.finished"), fg="#00ff88")
        else:
            wkg_str = f"{state.w_per_kg} w/kg" if state.w_per_kg is not None else "--- w/kg"
            self._line2.config(text=f"---w / {wkg_str}", fg="#00ff88")

        if state.current_interval:
            name = state.current_interval.name
            ri = state.current_interval.repeat_index
            rt = state.current_interval.repeat_total
            if ri and rt:
                self._line3.set_text(f"{name} {ri}/{rt}")
            else:
                self._line3.set_text(name)
        else:
            self._line3.set_text("")
