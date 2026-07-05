

import sys
import threading
import time

from core import perf
from core import win_windows

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    winmm = ctypes.WinDLL("winmm", use_last_error=True)

    PROCESS_SUSPEND_RESUME = 0x0800
    PROCESS_SET_INFORMATION = 0x0200
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _OPEN_RIGHTS = PROCESS_SUSPEND_RESUME | PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION

    IDLE_PRIORITY_CLASS = 0x00000040
    NORMAL_PRIORITY_CLASS = 0x00000020

    PROC_POWER_THROTTLING = 4
    PROC_POWER_THROTTLING_EXECUTION_SPEED = 0x1

    class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [("Version", wintypes.DWORD), ("ControlMask", wintypes.DWORD), ("StateMask", wintypes.DWORD)]

    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.SetPriorityClass.restype = wintypes.BOOL
    kernel32.SetProcessInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel32.SetProcessInformation.restype = wintypes.BOOL
    ntdll.NtSuspendProcess.argtypes = (wintypes.HANDLE,)
    ntdll.NtResumeProcess.argtypes = (wintypes.HANDLE,)


_MIN_CYCLE_MS = 10
_MAX_CYCLE_MS = 250
_MIN_QUOTA = 2
_MAX_QUOTA = 95
_REFRESH_S = 1.5
_BREATHE_EVERY_S = 5.0
_BREATHE_MS = 220
_RAM_CAP_MIN_MB = 150
_RAM_CAP_MAX_MB = 2000


class ThrottleEngine:
    def __init__(self, config, is_engine_running=None):
        self.config = config
        self._is_engine_running = is_engine_running or (lambda: True)
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._handles = {}
        self._capped = set()
        self._eco = set()
        self._timer_raised = False
        self._status = self._idle_status()

    def enabled(self) -> bool:
        return IS_WINDOWS and bool(self.config.settings.get("throttleEnabled", False))

    def _cycle_s(self) -> float:
        try:
            ms = int(self.config.settings.get("throttleCycleMs", 50))
        except (TypeError, ValueError):
            ms = 50
        return max(_MIN_CYCLE_MS, min(_MAX_CYCLE_MS, ms)) / 1000.0

    def _quota(self) -> int:
        try:
            q = int(self.config.settings.get("throttleQuota", 12))
        except (TypeError, ValueError):
            q = 12
        return max(_MIN_QUOTA, min(_MAX_QUOTA, q))

    def _focus_aware(self) -> bool:
        return bool(self.config.settings.get("throttleFocusAware", True))

    def _method(self) -> str:
        m = self.config.settings.get("throttleMethod", "efficiency")
        return "suspend" if m == "suspend" else "efficiency"

    def _only_when_running(self) -> bool:
        return bool(self.config.settings.get("throttleOnlyWhenRunning", False))

    def _engine_running(self) -> bool:
        try:
            return bool(self._is_engine_running())
        except Exception:
            return True

    def _breathe(self) -> bool:
        return bool(self.config.settings.get("throttleBreathe", True))

    def _ram_cap(self) -> bool:
        return bool(self.config.settings.get("throttleRamCap", False))

    def _ram_cap_mb(self) -> int:
        try:
            mb = int(self.config.settings.get("throttleRamCapMb", 400))
        except (TypeError, ValueError):
            mb = 400
        return max(_RAM_CAP_MIN_MB, min(_RAM_CAP_MAX_MB, mb))

    def _scope(self) -> str:
        s = self.config.settings.get("throttleScope", "onlyThese")
        return s if s in ("all", "allExcept", "onlyThese") else "onlyThese"

    def _selected_ids(self) -> set:
        raw = self.config.settings.get("throttleAccounts", []) or []
        out = set()
        for v in raw:
            try:
                out.add(int(v))
            except (TypeError, ValueError):
                pass
        return out

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
        if IS_WINDOWS and not self._timer_raised:
            try:
                winmm.timeBeginPeriod(1)
                self._timer_raised = True
            except Exception:
                pass
        ev = threading.Event()
        self._stop = ev
        self._thread = threading.Thread(target=self._loop, args=(ev,), daemon=True)
        self._thread.start()
        print(f"[Throttle] Started — {self._quota()}% quota, {int(self._cycle_s()*1000)} ms cycle.")

    def _stop_locked(self):
        if self._thread and self._thread.is_alive():
            print("[Throttle] Stopped.")
        self._stop.set()
        self._thread = None
        self._restore_all_eco()
        self._uncap_all()
        for pid in list(self._handles):
            self._release_handle(pid)
        if IS_WINDOWS and self._timer_raised:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._timer_raised = False
        self._status = self._idle_status()

    def _loop(self, ev):
        targets = {}
        last_refresh = 0.0
        last_breathe = time.monotonic()
        cyc = 0
        while not ev.is_set():
            now = time.monotonic()
            cyc += 1
            if now - last_refresh >= _REFRESH_S or not targets:
                targets = self._resolve_targets()
                self._prune_handles(set(targets))
                last_refresh = now

            if self._only_when_running() and not self._engine_running():
                for pid in list(self._handles):
                    self._resume(pid)
                self._restore_all_eco()
                self._uncap_all()
                self._publish([], [], [], paused=True)
                if ev.wait(0.4):
                    break
                continue

            if self._method() == "efficiency":
                fg_pid = win_windows.foreground_pid() if self._focus_aware() else 0
                pids = list(targets)
                held = [pid for pid in pids if pid == fg_pid]
                eco_now = []
                for pid in pids:
                    if pid in held:
                        if pid in self._eco:
                            self._set_eco(pid, False)
                            self._eco.discard(pid)
                    else:
                        if pid not in self._eco:
                            self._set_eco(pid, True)
                            self._eco.add(pid)
                        eco_now.append(pid)
                self._apply_ram_cap(pids, set(held))
                self._publish(pids, held, eco_now)
                if ev.wait(0.3):
                    break
                continue

            cycle = self._cycle_s()
            active = cycle * (self._quota() / 100.0)
            sleep_t = max(0.0, cycle - active)
            fg_pid = win_windows.foreground_pid() if self._focus_aware() else 0
            pids = list(targets)
            held = [pid for pid in pids if pid == fg_pid]

            for pid in pids:
                self._resume(pid)

            if self._breathe() and (now - last_breathe) >= _BREATHE_EVERY_S and pids:
                last_breathe = now
                self._apply_ram_cap(pids, set(held))
                self._publish(pids, held, throttled=[], breathing=True)
                if ev.wait(_BREATHE_MS / 1000.0):
                    break
                continue

            self._publish(pids, held, throttled=[])
            if ev.wait(active):
                break

            throttled = []
            for pid in pids:
                if pid in held:
                    continue
                if self._suspend(pid):
                    throttled.append(pid)
            self._publish(pids, held, throttled)

            self._apply_ram_cap(pids, set(held))

            if ev.wait(sleep_t):
                break

        self._restore_all_eco()
        self._uncap_all()
        for pid in list(self._handles):
            self._resume(pid)

    def _apply_ram_cap(self, pids, held_set):
        if not self._ram_cap():
            if self._capped:
                self._uncap_all()
            return
        want = [pid for pid in pids if pid not in held_set]
        to_cap = [pid for pid in want if pid not in self._capped]
        if to_cap:
            try:
                perf.cap_working_set(to_cap, self._ram_cap_mb() * 1048576)
                self._capped.update(to_cap)
            except Exception as e:
                print(f"[Throttle] RAM cap failed: {e}")
        to_lift = [pid for pid in self._capped if pid not in want]
        if to_lift:
            try:
                perf.uncap_working_set(to_lift)
            except Exception:
                pass
            for pid in to_lift:
                self._capped.discard(pid)

    def _uncap_all(self):
        if self._capped:
            try:
                perf.uncap_working_set(list(self._capped))
            except Exception:
                pass
            self._capped.clear()

    def _resolve_targets(self) -> dict:
        
        scope = self._scope()
        try:
            if scope == "onlyThese":
                selected = self._selected_ids()
                if not selected:
                    return {}
                resolved = win_windows.resolve_accounts(self.config.enabled_accounts())
                return {int(info["pid"]): aid for aid, info in resolved.items()
                        if info.get("pid") and aid in selected}

            all_pids = {int(pid) for _h, pid in win_windows.roblox_windows() if pid}
            if not all_pids:
                return {}
            acc_for_pid = {}
            except_pids = set()
            if scope == "allExcept":
                except_ids = self._selected_ids()
                resolved = win_windows.resolve_accounts(self.config.enabled_accounts())
                for aid, info in resolved.items():
                    pid = info.get("pid")
                    if pid:
                        acc_for_pid[int(pid)] = aid
                        if aid in except_ids:
                            except_pids.add(int(pid))
            return {pid: acc_for_pid.get(pid) for pid in all_pids if pid not in except_pids}
        except Exception as e:
            print(f"[Throttle] Window resolve failed: {e}")
            return {}

    def _handle(self, pid):
        h = self._handles.get(pid)
        if h:
            return h
        h = kernel32.OpenProcess(_OPEN_RIGHTS, False, pid)
        if not h:
            h = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if h:
            self._handles[pid] = h
        return h

    def _suspend(self, pid) -> bool:
        h = self._handle(pid)
        if not h:
            return False
        try:
            ntdll.NtSuspendProcess(h)
            return True
        except Exception:
            return False

    def _resume(self, pid):
        h = self._handle(pid)
        if not h:
            return
        try:
            ntdll.NtResumeProcess(h)
        except Exception:
            pass

    def _set_eco(self, pid, on) -> bool:
        h = self._handle(pid)
        if not h:
            return False
        try:
            kernel32.SetPriorityClass(h, IDLE_PRIORITY_CLASS if on else NORMAL_PRIORITY_CLASS)
            st = PROCESS_POWER_THROTTLING_STATE()
            st.Version = 1
            st.ControlMask = PROC_POWER_THROTTLING_EXECUTION_SPEED
            st.StateMask = PROC_POWER_THROTTLING_EXECUTION_SPEED if on else 0
            kernel32.SetProcessInformation(h, PROC_POWER_THROTTLING, ctypes.byref(st), ctypes.sizeof(st))
            return True
        except Exception:
            return False

    def _restore_all_eco(self):
        for pid in list(self._eco):
            self._set_eco(pid, False)
        self._eco.clear()

    def _release_handle(self, pid):
        h = self._handles.pop(pid, None)
        if not h:
            return
        try:
            if pid in self._eco:
                self._set_eco_handle(h, False)
                self._eco.discard(pid)
        except Exception:
            pass
        try:
            ntdll.NtResumeProcess(h)
        except Exception:
            pass
        try:
            kernel32.CloseHandle(h)
        except Exception:
            pass

    def _set_eco_handle(self, h, on):
        kernel32.SetPriorityClass(h, IDLE_PRIORITY_CLASS if on else NORMAL_PRIORITY_CLASS)
        st = PROCESS_POWER_THROTTLING_STATE()
        st.Version = 1
        st.ControlMask = PROC_POWER_THROTTLING_EXECUTION_SPEED
        st.StateMask = PROC_POWER_THROTTLING_EXECUTION_SPEED if on else 0
        kernel32.SetProcessInformation(h, PROC_POWER_THROTTLING, ctypes.byref(st), ctypes.sizeof(st))

    def _prune_handles(self, keep: set):
        for pid in list(self._handles):
            if pid not in keep:
                self._release_handle(pid)

    def _idle_status(self) -> dict:
        return {
            "supported": IS_WINDOWS,
            "enabled": self.enabled() if IS_WINDOWS else False,
            "running": False,
            "method": self._method() if IS_WINDOWS else "efficiency",
            "scope": self._scope() if IS_WINDOWS else "onlyThese",
            "cycleMs": self._cycle_s() * 1000 if IS_WINDOWS else 50,
            "quota": self._quota() if IS_WINDOWS else 12,
            "focusAware": self._focus_aware() if IS_WINDOWS else True,
            "onlyWhenRunning": self._only_when_running() if IS_WINDOWS else False,
            "breathe": self._breathe() if IS_WINDOWS else True,
            "ramCap": self._ram_cap() if IS_WINDOWS else False,
            "ramCapMb": self._ram_cap_mb() if IS_WINDOWS else 400,
            "breathing": False, "paused": False,
            "tracked": 0, "live": 0, "throttled": 0, "holds": 0, "capped": 0,
            "targetPids": [], "throttledPids": [], "heldPids": [],
        }

    def _publish(self, pids, held, throttled, breathing=False, paused=False):
        snap = {
            "supported": IS_WINDOWS,
            "enabled": True,
            "running": True,
            "method": self._method(),
            "scope": self._scope(),
            "cycleMs": round(self._cycle_s() * 1000),
            "quota": self._quota(),
            "focusAware": self._focus_aware(),
            "onlyWhenRunning": self._only_when_running(),
            "breathe": self._breathe(),
            "ramCap": self._ram_cap(),
            "ramCapMb": self._ram_cap_mb(),
            "breathing": bool(breathing),
            "paused": bool(paused),
            "tracked": len(pids),
            "live": len(pids),
            "throttled": len(throttled),
            "holds": len(held),
            "capped": len(self._capped),
            "targetPids": list(pids),
            "throttledPids": list(throttled),
            "heldPids": list(held),
        }
        with self._lock:
            self._status = snap

    def status(self) -> dict:
        with self._lock:
            snap = dict(self._status)
        snap["supported"] = IS_WINDOWS
        snap["enabled"] = self.enabled()
        snap["method"] = self._method()
        snap["scope"] = self._scope()
        snap["cycleMs"] = round(self._cycle_s() * 1000)
        snap["quota"] = self._quota()
        snap["focusAware"] = self._focus_aware()
        snap["onlyWhenRunning"] = self._only_when_running()
        snap["breathe"] = self._breathe()
        snap["ramCap"] = self._ram_cap()
        snap["ramCapMb"] = self._ram_cap_mb()
        if not snap.get("running"):
            snap["tracked"] = snap["live"] = snap["throttled"] = snap["holds"] = 0
            snap["capped"] = 0
            snap["breathing"] = False
            snap["targetPids"] = snap["throttledPids"] = snap["heldPids"] = []
        return snap
