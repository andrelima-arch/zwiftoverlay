import threading

from app.core.events import EventLoop, Signal


class FakeRoot:
    def __init__(self) -> None:
        self.owner = threading.get_ident()
        self.cancelled = []
        self.after_calls = []

    def after(self, ms, callback):
        if threading.get_ident() != self.owner:
            raise RuntimeError("main thread is not in main loop")
        timer_id = f"timer-{len(self.after_calls)}"
        self.after_calls.append((timer_id, ms, callback))
        return timer_id

    def after_cancel(self, timer_id):
        self.cancelled.append(timer_id)


def test_emit_safe_from_worker_thread_does_not_call_tk_after_directly():
    loop = EventLoop.get()
    loop.clear_root()
    root = FakeRoot()
    loop.set_root(root)
    signal = Signal()
    received = []
    signal.connect(lambda value: received.append(value))

    thread = threading.Thread(target=lambda: signal.emit_safe("ok"))
    thread.start()
    thread.join()

    assert received == []
    loop._drain_threadsafe_callbacks()
    assert received == ["ok"]

    loop.clear_root()
