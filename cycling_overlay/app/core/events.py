import logging
import queue
import threading
from typing import Callable

logger = logging.getLogger(__name__)


class Signal:
    def __init__(self, *args) -> None:
        self._callbacks: list[Callable] = []

    def connect(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def disconnect(self, callback: Callable) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.exception("Signal callback error")

    def emit_safe(self, *args, **kwargs) -> None:
        from app.core.events import EventLoop
        event_loop = EventLoop.get()
        for callback in self._callbacks:
            event_loop.call_soon_threadsafe(callback, *args, **kwargs)


class EventLoop:
    _instance = None

    def __init__(self) -> None:
        self._root = None
        self._timers: set[str] = set()
        self._owner_thread_id: int | None = None
        self._threadsafe_callbacks: queue.SimpleQueue[tuple[Callable, tuple, dict]] = queue.SimpleQueue()
        self._queue_pump_id: str | None = None
        self._closed = False

    @classmethod
    def get(cls) -> "EventLoop":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_root(self, root) -> None:
        self._root = root
        self._owner_thread_id = threading.get_ident()
        self._closed = False
        self._schedule_queue_pump()

    def call_later(self, ms: int, callback: Callable, *args) -> str | None:
        if self._root is None or self._closed:
            return None
        if self._owner_thread_id is not None and threading.get_ident() != self._owner_thread_id:
            self.call_soon_threadsafe(self.call_later, ms, callback, *args)
            return None
        timer_id = None

        def wrapped() -> None:
            if timer_id is not None:
                self._timers.discard(timer_id)
            if self._root is None or self._closed:
                return
            callback(*args)

        try:
            timer_id = self._root.after(ms, wrapped)
        except RuntimeError:
            self.call_soon_threadsafe(callback, *args)
            return None
        self._timers.add(timer_id)
        return timer_id

    def call_soon_threadsafe(self, callback: Callable, *args, **kwargs) -> None:
        if self._closed:
            return
        self._threadsafe_callbacks.put((callback, args, kwargs))

    def _schedule_queue_pump(self) -> None:
        if self._root is None or self._closed or self._queue_pump_id is not None:
            return
        if self._owner_thread_id is not None and threading.get_ident() != self._owner_thread_id:
            return

        def pump() -> None:
            self._queue_pump_id = None
            self._drain_threadsafe_callbacks()
            self._schedule_queue_pump()

        try:
            self._queue_pump_id = self._root.after(25, pump)
        except RuntimeError:
            self._queue_pump_id = None

    def _drain_threadsafe_callbacks(self) -> None:
        if self._closed:
            return
        while True:
            try:
                callback, args, kwargs = self._threadsafe_callbacks.get_nowait()
            except queue.Empty:
                break
            try:
                callback(*args, **kwargs)
            except Exception:
                logger.exception("EventLoop callback error")

    def cancel(self, timer_id: str | None) -> None:
        if self._root is not None and timer_id is not None:
            try:
                self._root.after_cancel(timer_id)
            except Exception:
                pass
        if timer_id is not None:
            self._timers.discard(timer_id)

    def clear_root(self) -> None:
        self._closed = True
        if self._queue_pump_id is not None:
            self.cancel(self._queue_pump_id)
            self._queue_pump_id = None
        for timer_id in list(self._timers):
            self.cancel(timer_id)
        self._root = None
        self._owner_thread_id = None
        while True:
            try:
                self._threadsafe_callbacks.get_nowait()
            except queue.Empty:
                break
