

import sys
import threading
import time

from . import perf
from . import win_windows


IS_WINDOWS = sys.platform == "win32"


class RobloxTrayCleanup:
    def __init__(
        self,
        *,
        poll_interval=0.5,
        launch_timeout=45.0,
        hidden_grace=7.0,
        never_visible_grace=45.0,
    ):
        self.poll_interval = float(poll_interval)
        self.launch_timeout = float(launch_timeout)
        self.hidden_grace = float(hidden_grace)
        self.never_visible_grace = float(never_visible_grace)

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread = None
        self._pending_launches = []
        self._tracked = {}

    @staticmethod
    def process_snapshot():
        if not IS_WINDOWS:
            return set()
        try:
            return set(perf.roblox_pids())
        except Exception:
            return set()

    def register_launch(self, previous_pids=None):
        
        if not IS_WINDOWS:
            return

        baseline = (
            set(previous_pids)
            if previous_pids is not None
            else self.process_snapshot()
        )
        now = time.monotonic()
        with self._lock:
            self._pending_launches.append(
                {
                    "baseline": baseline,
                    "registered_at": now,
                    "deadline": now + self.launch_timeout,
                }
            )
            self._ensure_thread_locked()

    def _ensure_thread_locked(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="roblox-tray-cleanup",
            daemon=True,
        )
        self._thread.start()

    def _run(self):
        while not self._stop_event.wait(self.poll_interval):
            now = time.monotonic()
            current_pids = self.process_snapshot()
            try:
                visible_pids = {
                    int(pid) for _hwnd, pid in win_windows.roblox_windows()
                }
            except Exception:
                visible_pids = set()

            self._scan(now, current_pids, visible_pids)

            with self._lock:
                if not self._pending_launches and not self._tracked:
                    self._thread = None
                    return

    def _scan(self, now, current_pids, visible_pids, terminate=None):
        
        current_pids = {int(pid) for pid in current_pids}
        visible_pids = {int(pid) for pid in visible_pids}
        terminate = terminate or self._terminate_tray_process

        to_terminate = []
        with self._lock:
            claimed_pids = set(self._tracked)
            still_pending = []
            for launch in self._pending_launches:
                candidates = sorted(
                    current_pids - launch["baseline"] - claimed_pids
                )
                if candidates:
                    pid = candidates[0]
                    claimed_pids.add(pid)
                    self._tracked[pid] = {
                        "first_seen": now,
                        "seen_window": pid in visible_pids,
                        "hidden_since": None,
                    }
                elif now < launch["deadline"]:
                    still_pending.append(launch)
            self._pending_launches = still_pending




            for pid in visible_pids & current_pids:
                state = self._tracked.setdefault(
                    pid,
                    {
                        "first_seen": now,
                        "seen_window": False,
                        "hidden_since": None,
                    },
                )
                state["seen_window"] = True
                state["hidden_since"] = None

            for pid, state in list(self._tracked.items()):
                if pid not in current_pids:
                    self._tracked.pop(pid, None)
                    continue

                if pid in visible_pids:
                    state["seen_window"] = True
                    state["hidden_since"] = None
                    continue



                if not state["seen_window"]:
                    if now - state["first_seen"] >= self.never_visible_grace:
                        self._tracked.pop(pid, None)
                        to_terminate.append(pid)
                    continue

                if state["hidden_since"] is None:
                    state["hidden_since"] = now
                    continue

                if now - state["hidden_since"] >= self.hidden_grace:
                    self._tracked.pop(pid, None)
                    to_terminate.append(pid)

        for pid in to_terminate:
            terminate(pid)

    @staticmethod
    def _terminate_tray_process(pid):
        try:
            if win_windows.close_pid_gracefully(pid, timeout=3.0):
                win_windows.refresh_notification_area()
                print(f"[Roblox] Closed leftover tray process {pid}")
        except Exception as error:
            print(f"[Roblox] Could not close tray process {pid}: {error}")

    def stop(self):
        
        self._stop_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._thread = None
            self._pending_launches.clear()
            self._tracked.clear()


cleanup = RobloxTrayCleanup()
