

import threading

from core import bridge as eel
from . import perf

_MIN_MINUTES = 1
_MAX_MINUTES = 24 * 60


class RamTrimmer:
    def __init__(self, config, is_engine_running=None):
        self.config = config
        self._is_engine_running = is_engine_running or (lambda: True)
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def enabled(self) -> bool:
        return bool(self.config.settings.get("ramTrimEnabled", False))

    def _interval_seconds(self) -> int:
        try:
            minutes = int(self.config.settings.get("ramTrimInterval", 60))
        except (TypeError, ValueError):
            minutes = 60
        minutes = max(_MIN_MINUTES, min(_MAX_MINUTES, minutes))
        return minutes * 60

    def sync(self):
        
        with self._lock:
            self._stop_locked()
            if self.enabled():
                self._start_locked()

    def start(self):
        with self._lock:
            if self.enabled():
                self._start_locked()

    def stop(self):
        with self._lock:
            self._stop_locked()

    def _start_locked(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[RamTrim] Started — every {self._interval_seconds() // 60} min.")

    def _stop_locked(self):
        if self._thread and self._thread.is_alive():
            print("[RamTrim] Stopped.")
        self._stop.set()
        self._thread = None

    def _loop(self):
        while not self._stop.wait(self._interval_seconds()):
            if self._stop.is_set() or not self.enabled():
                break
            try:
                if not self._is_engine_running():
                    continue
            except Exception:
                pass
            self._fire()

    def _fire(self):
        try:
            result = perf.trim_system_ram()
        except Exception as e:
            print(f"[RamTrim] Trim failed: {e}")
            return
        if not result or not result.get("ok"):
            return
        notify_ram_trimmed(result.get("freedBytes", 0), result.get("count", 0))

    def trim_now(self) -> dict:
        
        try:
            result = perf.trim_system_ram()
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if result and result.get("ok"):
            notify_ram_trimmed(result.get("freedBytes", 0), result.get("count", 0))
        return result or {"ok": False}


def notify_ram_trimmed(freed_bytes: int, count: int = 0):
    
    try:
        eel.js_on_ram_trimmed(int(freed_bytes or 0), int(count or 0))()
    except Exception as e:
        print(f"[RamTrim] Notify failed: {e}")
