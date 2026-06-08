import tkinter as tk
import tkinter.font as tkfont

from app.ui.i18n import normalize_language, t

COUNTDOWN_SECONDS = 10


class MarqueeLabel(tk.Canvas):
    def __init__(self, parent, text="", fg="white", bg="#000000", font=("Consolas", 10, "bold"), **kwargs):
        super().__init__(parent, bg=bg, highlightthickness=0, height=20, **kwargs)
        self._text = text
        self._fg = fg
        self._font = tkfont.Font(font=font)
        self._x = 0
        self._after_id = None
        self._item = self.create_text(0, 10, text=text, fill=fg, font=self._font, anchor="w")
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
        self.coords(self._item, self._x, 10)

    def _tick(self) -> None:
        width = self.winfo_width()
        text_width = self._font.measure(self._text)
        if self._text and text_width > width:
            self._x -= 2
            if self._x < -text_width:
                self._x = width
            self.coords(self._item, self._x, 10)
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
    def __init__(self, language: str = "en", on_skip_forward=None, on_skip_backward=None) -> None:
        super().__init__()
        self._language = normalize_language(language)
        self._on_skip_forward = on_skip_forward
        self._on_skip_backward = on_skip_backward
        self._countdown_visible = False

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-transparentcolor", "")
        self.configure(bg="black")

        self._drag_x = None
        self._drag_y = None

        self._main = tk.Frame(self, bg="black")
        self._main.pack(fill="both", expand=True)

        self._info_frame = tk.Frame(self._main, bg="black")
        self._info_frame.grid(row=0, column=0, sticky="nsew")

        self._countdown_frame = tk.Frame(self._main, bg="black", width=75)
        self._countdown_label = tk.Label(
            self._countdown_frame,
            text="",
            fg="#ffaa00",
            bg="black",
            font=("Consolas", 36, "bold"),
            anchor="center",
        )
        self._countdown_label.pack(expand=True, fill="both", padx=1)

        self._line1 = tk.Label(
            self._info_frame, text="---w / ---rpm / ---bpm",
            fg="white", bg="#000000",
            font=("Consolas", 14, "bold"),
            anchor="center",
        )
        self._line1.pack(fill="x", padx=(0, 0), pady=(4, 1))

        self._line2 = tk.Label(
            self._info_frame, text="---w / --- w/kg / ---rpm",
            fg="#00ff88", bg="#000000",
            font=("Consolas", 14, "bold"),
            anchor="center",
        )
        self._line2.pack(fill="x", padx=(0, 0), pady=1)

        self._nav_frame = tk.Frame(self._info_frame, bg="black")

        self._btn_prev = tk.Button(
            self._nav_frame, text="◀",
            fg="#3399ff", bg="#111111", activebackground="#222222", activeforeground="#3399ff",
            font=("Consolas", 10, "bold"),
            relief="flat", borderwidth=0,
            command=self._on_skip_backward,
            padx=6, pady=1,
        )
        self._btn_prev.pack(side="left", padx=(0, 4))

        self._btn_next = tk.Button(
            self._nav_frame, text="▶",
            fg="#3399ff", bg="#111111", activebackground="#222222", activeforeground="#3399ff",
            font=("Consolas", 10, "bold"),
            relief="flat", borderwidth=0,
            command=self._on_skip_forward,
            padx=6, pady=1,
        )
        self._btn_next.pack(side="left", padx=(4, 0))

        self._line4 = MarqueeLabel(
            self._info_frame,
            text="",
            fg="#ffaa00", bg="#000000",
            font=("Consolas", 10, "bold"),
        )
        self._line4.pack(fill="x", padx=(0, 0), pady=(1, 4))

        self._nav_frame.pack_forget()

        self._bind_drag(self)
        self._bind_drag(self._main)
        self._bind_drag(self._info_frame)
        self._bind_drag(self._line1)
        self._bind_drag(self._line2)
        self._bind_drag(self._countdown_frame)
        self._bind_drag(self._countdown_label)

        self.geometry("+{}+{}".format(
            self.winfo_screenwidth() - 320,
            20,
        ))
        self.update_idletasks()
        self._resize()

    def _bind_drag(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._on_press)
        widget.bind("<B1-Motion>", self._on_drag)

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

    def _on_skip_forward(self) -> None:
        if self._on_skip_forward:
            self._on_skip_forward()

    def _on_skip_backward(self) -> None:
        if self._on_skip_backward:
            self._on_skip_backward()

    def _resize(self) -> None:
        self.update_idletasks()
        w = self._info_frame.winfo_reqwidth()
        if self._countdown_visible:
            w += self._countdown_frame.winfo_reqwidth() + 4
        h = self._info_frame.winfo_reqheight() + 4
        x = self.winfo_x()
        y = self.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _show_countdown(self, remaining: int) -> None:
        text = f"0:{remaining:02d}" if remaining >= 10 else f"0:0{remaining}"
        self._countdown_label.configure(text=text)
        if not self._countdown_visible:
            self._countdown_visible = True
            self._countdown_frame.grid(row=0, column=1, sticky="ns", padx=(0, 4))
            self._resize()

    def _hide_countdown(self) -> None:
        if self._countdown_visible:
            self._countdown_visible = False
            self._countdown_label.configure(text="")
            self._countdown_frame.grid_remove()
            self._resize()

    def update_state(self, state) -> None:
        from app.models.app_state import EngineState
        sd = state.sensor_data

        in_workout = state.engine_state in (EngineState.RUNNING, EngineState.PAUSED, EngineState.BETWEEN_INTERVALS)
        if in_workout and not self._nav_frame.winfo_ismapped():
            self._nav_frame.pack(padx=(0, 0), pady=1, before=self._line4)
        elif not in_workout and self._nav_frame.winfo_ismapped():
            self._nav_frame.pack_forget()

        remaining = state.interval_remaining_seconds

        if state.engine_state == EngineState.PAUSED:
            self._hide_countdown()
            self._line1.config(text="---w / ---rpm / ---bpm", fg="white")
            self._line2.config(text=self._text("overlay.paused"), fg="#ffaa00")
            if state.current_interval:
                pct = int(state.interval_progress_percent * 100)
                self._line4.set_text(self._text("overlay.interval_progress", pct=pct))
            self._resize()
            return

        if state.engine_state == EngineState.BETWEEN_INTERVALS:
            self._hide_countdown()
            self._line1.config(text="---w / ---rpm / ---bpm", fg="white")
            next_name = ""
            if state.current_interval:
                next_name = state.current_interval.name
                ri = state.current_interval.repeat_index
                rt = state.current_interval.repeat_total
                if ri and rt:
                    next_name = f"{next_name} {ri}/{rt}"
            self._line2.config(text=self._text("overlay.next", name=next_name), fg="#ffaa00")
            self._line4.set_text(self._text("overlay.pedal_start"))
            self._resize()
            return

        power_str = f"{sd.power}w" if sd.power is not None else "---w"
        cadence_str = f"{sd.cadence}rpm" if sd.cadence is not None else "---rpm"
        hr_str = f"{sd.heart_rate}bpm" if sd.heart_rate is not None else "---bpm"
        line1_text = f"{power_str} / {cadence_str} / {hr_str}"

        if state.engine_state == EngineState.RUNNING and 1 <= remaining <= COUNTDOWN_SECONDS:
            self._show_countdown(remaining)
        else:
            self._hide_countdown()

        if state.engine_state == EngineState.RUNNING and 1 <= remaining <= COUNTDOWN_SECONDS:
            self._line1.config(text=line1_text, fg="#ffaa00")
        else:
            self._line1.config(text=line1_text, fg="white")

        if state.current_interval and state.current_target_power is not None:
            target = state.current_interval.target_display
            wkg_str = f"{state.w_per_kg} w/kg" if state.w_per_kg is not None else "--- w/kg"
            rpm_target = state.current_interval.cadence_target
            rpm_str = f"{rpm_target}rpm" if rpm_target is not None else "---rpm"
            self._line2.config(text=f"{target} / {wkg_str} / {rpm_str}", fg="#00ff88")
        elif state.current_interval is None and state.engine_state == EngineState.FINISHED:
            self._hide_countdown()
            self._line2.config(text=self._text("overlay.finished"), fg="#00ff88")
        else:
            wkg_str = f"{state.w_per_kg} w/kg" if state.w_per_kg is not None else "--- w/kg"
            self._line2.config(text=f"---w / {wkg_str} / ---rpm", fg="#00ff88")

        if state.current_interval:
            name = state.current_interval.name
            ri = state.current_interval.repeat_index
            rt = state.current_interval.repeat_total
            if ri and rt:
                self._line4.set_text(f"{name} {ri}/{rt}")
            else:
                self._line4.set_text(name)
        else:
            self._line4.set_text("")

        self._resize()
