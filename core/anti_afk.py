

import sys
import threading
import time

from . import win_input, win_windows


IS_WINDOWS = sys.platform == "win32"


def _roblox_windows():
    
    if not IS_WINDOWS:
        return []
    try:
        return [(int(hwnd), int(pid)) for hwnd, pid in win_windows.roblox_windows()]
    except Exception:
        return []


def _focus_verified(hwnd, timeout=2.5):
    
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        win_windows.focus_hwnd(hwnd)
        if win_windows.foreground_hwnd() == int(hwnd):
            return True
        time.sleep(0.08)
    return False


def _send_action(action):
    if action == "zoom":
        win_input.press_key("i", settle=0.08)
        win_input.press_key("o", settle=0.08)
    else:
        win_input.press_key("space", settle=0.08)


def _run_cycle(action, settle=0.35, throttler=None):
    
    previous_window = win_windows.foreground_hwnd() if IS_WINDOWS else 0
    targets = list(dict.fromkeys(_roblox_windows()))
    successful = 0
    throttle_held = False

    try:
        if throttler is not None:
            throttle_held = bool(throttler.begin_input_hold())

        for hwnd, _pid in targets:
            if not _focus_verified(hwnd):
                print(f"[AntiAfk] Could not focus Roblox window {hwnd}; skipping it.")
                continue



            time.sleep(max(0.12, float(settle)))
            if win_windows.foreground_hwnd() != hwnd:
                if not _focus_verified(hwnd, timeout=1.5):
                    continue

            _send_action(action)
            time.sleep(0.15)
            successful += 1
    finally:
        if previous_window and win_windows.foreground_hwnd() != previous_window:
            win_windows.focus_hwnd(previous_window)
        if throttle_held:
            throttler.end_input_hold()

    if targets:
        print(f"[AntiAfk] Verified input sent to {successful}/{len(targets)} Roblox windows.")
    return successful, len(targets)


def focus_roblox():
    
    targets = _roblox_windows()
    if not targets:
        return False
    return _focus_verified(targets[0][0])


class AntiAfk:
    def __init__(self, config, is_running):
        self.config = config
        self._is_running = is_running
        self._stop = threading.Event()
        self._thread = None
        self._throttler = None
        self._cycle_lock = threading.Lock()
        self._action_lock = None

    def set_throttler(self, throttler):
        self._throttler = throttler

    def set_action_lock(self, action_lock):
        
        self._action_lock = action_lock

    def enabled(self):
        return bool(self.config.settings.get("antiAfkEnabled", False))

    def standalone(self):
        return bool(self.config.settings.get("antiAfkStandalone", False))

    def _action(self):
        value = self.config.settings.get("antiAfkAction", "space")
        return "zoom" if value == "zoom" else "space"

    def _interval(self):
        try:
            value = int(self.config.settings.get("antiAfkInterval", 300))
        except (TypeError, ValueError):
            value = 300
        return max(30, min(900, value))

    def _settle(self):
        if self.config.settings.get("throttleEnabled", False):
            return 0.45
        return 0.25

    def start(self):
        if not IS_WINDOWS or not self.enabled():
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="anti-afk",
            daemon=True,
        )
        self._thread.start()
        print("[AntiAfk] Started.")

    def stop(self):
        thread = self._thread
        if thread:
            print("[AntiAfk] Stopped.")
        self._stop.set()
        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=0.5)
        if self._thread is thread:
            self._thread = None

    def _loop(self):
        self._fire()
        while not self._stop.wait(self._interval()):
            if self._stop.is_set():
                break
            self._fire()

    def _fire(self):
        if self._stop.is_set() or not self.enabled():
            return
        if not (self._is_running() or self.standalone()):
            return
        self._run_safely()

    def _run_safely(self):
        if not self._cycle_lock.acquire(blocking=False):
            return
        try:
            if self._action_lock is None:
                _run_cycle(self._action(), self._settle(), self._throttler)
            else:
                with self._action_lock:
                    _run_cycle(self._action(), self._settle(), self._throttler)
        except Exception as error:
            print(f"[AntiAfk] Cycle failed: {error}")
        finally:
            self._cycle_lock.release()

    def fire_now(self):
        if not IS_WINDOWS or not self.enabled():
            return
        self._run_safely()
