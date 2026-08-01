

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
    PROCESS_SET_INFORMATION = 0x0200
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _OPEN_RIGHTS = PROCESS_SET_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION
    PROCESS_TERMINATE = 0x0001
    PROCESS_SET_QUOTA = 0x0100
    _JOB_PROCESS_RIGHTS = PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_QUERY_LIMITED_INFORMATION

    IDLE_PRIORITY_CLASS = 0x00000040
    NORMAL_PRIORITY_CLASS = 0x00000020

    PROC_POWER_THROTTLING = 4
    PROC_POWER_THROTTLING_EXECUTION_SPEED = 0x1

    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x1
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x4
    JobObjectCpuRateControlInformation = 15
    ERROR_ALREADY_EXISTS = 183

    class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
        _fields_ = [("Version", wintypes.DWORD), ("ControlMask", wintypes.DWORD), ("StateMask", wintypes.DWORD)]

    class JOBOBJECT_CPU_RATE_CONTROL_INFORMATION(ctypes.Structure):
        _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]

    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.SetPriorityClass.restype = wintypes.BOOL
    kernel32.SetProcessInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    kernel32.SetProcessInformation.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.IsProcessInJob.argtypes = (wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL))
    kernel32.IsProcessInJob.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = (
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    )
    kernel32.SetInformationJobObject.restype = wintypes.BOOL


_MIN_CYCLE_MS = 10
_MAX_CYCLE_MS = 250
_MIN_QUOTA = 2
_MAX_QUOTA = 95
_REFRESH_S = 1.5
_RAM_CAP_MIN_MB = 150
_RAM_CAP_MAX_MB = 2000
_FOCUS_WARMUP_S = 3.0


class ThrottleEngine:
    def __init__(self, config, is_engine_running=None):
        self.config = config
        self._is_engine_running = is_engine_running or (lambda: True)
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._focus_lock = threading.Lock()
        self._job_lock = threading.RLock()



        self._state_lock = threading.RLock()
        self._handles = {}
        self._cpu_jobs = {}
        self._job_rates = {}




        self._job_failures = {}
        self._capped = set()
        self._eco = set()
        self._benchmark_active = False
        self._benchmark_settings = None
        self._benchmark_targets = None
        self._input_hold = threading.Event()
        self._input_hold_lock = threading.Lock()
        self._input_hold_count = 0
        self._focus_leases = {}
        self._last_foreground_pid = 0
        self._status = self._idle_status()

    def _setting(self, key, default=None):
        settings = self._benchmark_settings
        if settings is not None:
            return settings.get(key, default)
        return self.config.settings.get(key, default)

    def enabled(self) -> bool:
        return IS_WINDOWS and bool(self.config.settings.get("throttleEnabled", False))

    def _cycle_s(self) -> float:
        try:
            ms = int(self._setting("throttleCycleMs", 50))
        except (TypeError, ValueError):
            ms = 50
        return max(_MIN_CYCLE_MS, min(_MAX_CYCLE_MS, ms)) / 1000.0

    def _quota(self) -> int:
        try:
            q = int(self._setting("throttleQuota", 12))
        except (TypeError, ValueError):
            q = 12
        return max(_MIN_QUOTA, min(_MAX_QUOTA, q))

    def _focus_aware(self) -> bool:
        return bool(self._setting("throttleFocusAware", True))

    def _method(self) -> str:
        m = self._setting("throttleMethod", "efficiency")


        return "cpuLimit" if m in ("cpuLimit", "suspend") else "efficiency"

    def _only_when_running(self) -> bool:
        return bool(self._setting("throttleOnlyWhenRunning", False))

    def _engine_running(self) -> bool:
        try:
            return bool(self._is_engine_running())
        except Exception:
            return True

    def _breathe(self) -> bool:
        return bool(self._setting("throttleBreathe", True))

    def _ram_cap(self) -> bool:
        return bool(self._setting("throttleRamCap", False))

    def _ram_cap_mb(self) -> int:
        try:
            mb = int(self._setting("throttleRamCapMb", 400))
        except (TypeError, ValueError):
            mb = 400
        return max(_RAM_CAP_MIN_MB, min(_RAM_CAP_MAX_MB, mb))

    def _scope(self) -> str:
        s = self._setting("throttleScope", "onlyThese")
        return s if s in ("all", "allExcept", "onlyThese") else "onlyThese"

    def _selected_ids(self) -> set:
        raw = self._setting("throttleAccounts", []) or []
        out = set()
        for v in raw:
            try:
                out.add(int(v))
            except (TypeError, ValueError):
                pass
        return out

    def sync(self):
        
        with self._lock:
            if self._benchmark_active:
                return
            if not self._stop_locked(preserve_input_hold=True):
                return
            if self.enabled():
                self._start_locked()

    def start(self):
        with self._lock:
            if self._benchmark_active:
                return
            if self.enabled():
                self._start_locked()

    def stop(self):
        with self._lock:
            self._stop_locked()

    def prepare_benchmark(self) -> bool:
        
        if not IS_WINDOWS:
            return False
        with self._lock:
            if self._benchmark_active:
                return False
            self._benchmark_active = True
            if not self._stop_locked(preserve_input_hold=True):
                self._benchmark_active = False
                return False
            return True

    def apply_benchmark(self, pids, settings) -> bool:
        
        with self._lock:
            if not self._benchmark_active:
                return False
            self._benchmark_targets = {int(pid) for pid in pids or [] if int(pid) > 0}
            self._benchmark_settings = dict(settings or {})
            self._start_locked()
            return True

    def restore_after_benchmark(self):
        
        with self._lock:
            if not self._benchmark_active:
                return
            if not self._stop_locked(preserve_input_hold=True):
                return
            self._benchmark_settings = None
            self._benchmark_targets = None
            self._benchmark_active = False
            if self.enabled():
                self._start_locked()

    def begin_input_hold(self):
        
        if not IS_WINDOWS or not self.enabled():
            return False
        with self._input_hold_lock:
            self._input_hold_count += 1
            self._input_hold.set()
        self._resume_input_targets()



        time.sleep(0.05)
        self._resume_input_targets()
        return True

    def end_input_hold(self):
        
        with self._input_hold_lock:
            self._input_hold_count = max(0, self._input_hold_count - 1)
            if self._input_hold_count == 0:
                self._input_hold.clear()

    def warm_up_process(self, pid, seconds=3.0):
        
        if not IS_WINDOWS or not self.enabled() or self._method() != "cpuLimit":
            return False
        try:
            pid = int(pid)
            seconds = max(0.0, float(seconds))
        except (TypeError, ValueError):
            return False
        if pid <= 0:
            return False

        now = time.monotonic()


        with self._focus_lock:
            self._focus_leases[pid] = max(
                self._focus_leases.get(pid, 0.0),
                now + seconds + _FOCUS_WARMUP_S,
            )
        with self._state_lock:
            self._set_job_cpu_rate(pid, None)
            if pid in self._eco and self._set_eco(pid, False):
                self._eco.discard(pid)
            if pid in self._capped:
                try:
                    restored = perf.uncap_working_set([pid]) > 0
                except Exception:
                    restored = False
                if restored:
                    self._capped.discard(pid)

        if seconds:
            time.sleep(seconds)
        return True

    def _resume_input_targets(self):
        with self._state_lock:
            self._uncap_all_cpu_jobs()
            self._restore_all_eco()
            self._uncap_all()

    def _start_locked(self):
        if self._thread and self._thread.is_alive():
            return
        ev = threading.Event()
        self._stop = ev
        self._thread = threading.Thread(target=self._loop, args=(ev,), daemon=True)
        self._thread.start()
        label = "CPU rate control" if self._method() == "cpuLimit" else "Efficiency mode"
        print(f"[Throttle] Started — {label}, {self._quota()}% background budget.")

    def _stop_locked(self, preserve_input_hold=False):
        thread = self._thread
        if thread and thread.is_alive():
            print("[Throttle] Stopped.")
        if not preserve_input_hold:
            with self._input_hold_lock:
                self._input_hold_count = 0
                self._input_hold.clear()
        self._stop.set()
        with self._focus_lock:
            self._focus_leases.clear()
            self._last_foreground_pid = 0
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        if thread and thread.is_alive() and thread is not threading.current_thread():


            print("[Throttle] Worker did not stop in time; deferring handle cleanup.")
            self._thread = thread
            return False
        self._thread = None
        with self._state_lock:
            self._uncap_all_cpu_jobs()
            self._restore_all_eco()
            self._uncap_all()
            for pid in set(self._handles) | set(self._cpu_jobs):
                self._release_handle(pid)
        with self._status_lock:
            self._status = self._idle_status()
        return True

    def _loop(self, ev):
        try:
            self._run_loop(ev)
        except Exception as exc:
            print(f"[Throttle] Worker stopped after an unexpected error: {exc}")
        finally:


            try:
                self._resume_input_targets()
            except Exception:
                pass

    def _run_loop(self, ev):
        targets = {}
        last_refresh = 0.0
        while not ev.is_set():
            now = time.monotonic()
            if now - last_refresh >= _REFRESH_S:
                targets = self._resolve_targets()
                with self._state_lock:
                    self._prune_handles(set(targets))
                last_refresh = now

            if self._input_hold.is_set():
                self._resume_input_targets()
                self._publish(list(targets), list(targets), [], paused=True)
                if ev.wait(0.03):
                    break
                continue

            if self._only_when_running() and not self._engine_running():
                self._resume_input_targets()
                self._publish([], [], [], paused=True)
                if ev.wait(0.4):
                    break
                continue

            if self._method() == "efficiency":
                fg_pid = win_windows.foreground_pid() if self._focus_aware() else 0
                pids = list(targets)
                held = [pid for pid in pids if pid == fg_pid]
                eco_now = []
                with self._state_lock:
                    for pid in pids:
                        if pid in held:
                            if pid in self._eco and self._set_eco(pid, False):
                                self._eco.discard(pid)
                        else:
                            if pid not in self._eco and self._set_eco(pid, True):
                                self._eco.add(pid)
                            if pid in self._eco:
                                eco_now.append(pid)
                    self._apply_ram_cap(pids, set(held))
                self._publish(pids, held, eco_now)
                if ev.wait(0.3):
                    break
                continue

            fg_pid = win_windows.foreground_pid() if self._focus_aware() else 0
            pids = list(targets)
            now = time.monotonic()
            held = self._focus_held_pids(pids, fg_pid, now)
            held_set = set(held)
            limited = []
            with self._state_lock:
                for pid in pids:
                    if self._input_hold.is_set() or ev.is_set():


                        break
                    if pid in held_set:
                        self._set_job_cpu_rate(pid, None)
                        if pid in self._eco and self._set_eco(pid, False):
                            self._eco.discard(pid)
                        continue
                    if self._set_job_cpu_rate(pid, self._quota()):
                        limited.append(pid)
                        if pid in self._eco and self._set_eco(pid, False):
                            self._eco.discard(pid)
                    else:


                        if pid not in self._eco and self._set_eco(pid, True):
                            self._eco.add(pid)
                        if pid in self._eco:
                            limited.append(pid)

            if self._input_hold.is_set():
                self._resume_input_targets()
                self._publish(pids, pids, [], paused=True)
                if ev.wait(0.03):
                    break
                continue

            with self._state_lock:
                self._apply_ram_cap(pids, held_set)
            self._publish(pids, held, limited)

            if ev.wait(0.05):
                break

    def _apply_ram_cap(self, pids, held_set):
        if not self._ram_cap():
            if self._capped:
                self._uncap_all()
            return
        want = [pid for pid in pids if pid not in held_set]
        to_cap = [pid for pid in want if pid not in self._capped]
        for pid in to_cap:
            try:
                if perf.cap_working_set([pid], self._ram_cap_mb() * 1048576) > 0:
                    self._capped.add(pid)
            except Exception as e:
                print(f"[Throttle] RAM cap failed: {e}")
        to_lift = [pid for pid in self._capped if pid not in want]
        for pid in to_lift:
            try:
                restored = perf.uncap_working_set([pid]) > 0
            except Exception:
                restored = False
            if restored:
                self._capped.discard(pid)

    def _uncap_all(self):
        for pid in list(self._capped):
            try:
                restored = perf.uncap_working_set([pid]) > 0
            except Exception:
                restored = False
            if restored:
                self._capped.discard(pid)

    def _resolve_targets(self) -> dict:
        
        if self._benchmark_targets is not None:
            return {pid: None for pid in self._benchmark_targets}
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

    def _focus_held_pids(self, pids, foreground_pid, now):
        
        pids = list(pids)
        target_set = set(pids)
        with self._focus_lock:
            if foreground_pid != self._last_foreground_pid:
                self._last_foreground_pid = foreground_pid
                if foreground_pid in target_set:
                    self._focus_leases[foreground_pid] = now + _FOCUS_WARMUP_S
            self._focus_leases = {
                pid: deadline
                for pid, deadline in self._focus_leases.items()
                if deadline > now and pid in target_set
            }
            leases = dict(self._focus_leases)
        return [
            pid for pid in pids
            if pid == foreground_pid or leases.get(pid, 0.0) > now
        ]

    @staticmethod
    def _cpu_job_name(pid):


        return f"Local\\SolRichCpuRate_{int(pid)}"

    def _ensure_cpu_job(self, pid):
        
        pid = int(pid)
        existing = self._cpu_jobs.get(pid)
        if existing:
            return existing

        retry_after = self._job_failures.get(pid, 0.0)
        if retry_after > time.monotonic():
            return None

        ctypes.set_last_error(0)
        job = kernel32.CreateJobObjectW(None, self._cpu_job_name(pid))
        reopened_existing_job = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if not job:
            if not retry_after:
                print(f"[Throttle] Could not create CPU-rate job for PID {pid}; using Efficiency fallback.")
            self._job_failures[pid] = time.monotonic() + 10.0
            return None

        process = kernel32.OpenProcess(_JOB_PROCESS_RIGHTS, False, pid)
        if not process:
            kernel32.CloseHandle(job)
            if not retry_after:
                print(f"[Throttle] Could not open PID {pid} for CPU-rate control; using Efficiency fallback.")
            self._job_failures[pid] = time.monotonic() + 10.0
            return None

        try:
            already_assigned = wintypes.BOOL(False)
            query_ok = bool(kernel32.IsProcessInJob(process, job, ctypes.byref(already_assigned)))
            if not (query_ok and already_assigned.value):
                if not kernel32.AssignProcessToJobObject(job, process):
                    error = ctypes.get_last_error()
                    kernel32.CloseHandle(job)
                    if not retry_after:
                        print(f"[Throttle] PID {pid} rejected CPU-rate job (Windows error {error}); "
                              "using Efficiency fallback.")
                    self._job_failures[pid] = time.monotonic() + 10.0
                    return None
        finally:
            kernel32.CloseHandle(process)

        self._cpu_jobs[pid] = job




        self._job_rates[pid] = None if reopened_existing_job else 0
        self._job_failures.pop(pid, None)
        return job

    def _set_job_cpu_rate(self, pid, percent=None):
        
        with self._job_lock:
            pid = int(pid)
            job = self._cpu_jobs.get(pid)
            if not job:
                job = self._ensure_cpu_job(pid)
            if not job:
                return False

            wanted = 0 if percent is None else max(1, min(100, int(percent)))
            if self._job_rates.get(pid) == wanted:
                return True

            info = JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
            if wanted:
                info.ControlFlags = (
                    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
                    | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
                )
                info.CpuRate = wanted * 100
            else:
                info.ControlFlags = 0
                info.CpuRate = 0

            ok = bool(kernel32.SetInformationJobObject(
                job,
                JobObjectCpuRateControlInformation,
                ctypes.byref(info),
                ctypes.sizeof(info),
            ))
            if ok:
                self._job_rates[pid] = wanted
            return ok

    def _uncap_all_cpu_jobs(self):
        for pid in list(self._cpu_jobs):
            self._set_job_cpu_rate(pid, None)

    def _release_cpu_job(self, pid):
        with self._job_lock:
            pid = int(pid)
            job = self._cpu_jobs.get(pid)
            if not job:
                return


            restored = self._set_job_cpu_rate(pid, None)
            if not restored:


                restored = self._set_job_cpu_rate(pid, 100)
            if not restored:
                print(f"[Throttle] Could not restore CPU rate for PID {pid}; will retry cleanup.")
                return False
            self._cpu_jobs.pop(pid, None)
            self._job_rates.pop(pid, None)
            try:
                kernel32.CloseHandle(job)
            except Exception:
                pass
            return True

    def _handle(self, pid):
        h = self._handles.get(pid)
        if h:
            return h
        h = kernel32.OpenProcess(_OPEN_RIGHTS, False, pid)
        if h:
            self._handles[pid] = h
        return h

    def _set_eco(self, pid, on) -> bool:
        h = self._handle(pid)
        if not h:
            return False
        try:
            priority_ok = bool(kernel32.SetPriorityClass(
                h, IDLE_PRIORITY_CLASS if on else NORMAL_PRIORITY_CLASS,
            ))
            st = PROCESS_POWER_THROTTLING_STATE()
            st.Version = 1
            st.ControlMask = PROC_POWER_THROTTLING_EXECUTION_SPEED
            st.StateMask = PROC_POWER_THROTTLING_EXECUTION_SPEED if on else 0
            power_ok = bool(kernel32.SetProcessInformation(
                h, PROC_POWER_THROTTLING, ctypes.byref(st), ctypes.sizeof(st),
            ))
            ok = priority_ok and power_ok
            if on and not ok:


                kernel32.SetPriorityClass(h, NORMAL_PRIORITY_CLASS)
                st.StateMask = 0
                kernel32.SetProcessInformation(
                    h, PROC_POWER_THROTTLING, ctypes.byref(st), ctypes.sizeof(st),
                )
            return ok
        except Exception:
            return False

    def _restore_all_eco(self):
        for pid in list(self._eco):
            if self._set_eco(pid, False):
                self._eco.discard(pid)

    def _release_handle(self, pid):
        self._release_cpu_job(pid)
        h = self._handles.pop(pid, None)
        if not h and pid in self._eco:



            h = kernel32.OpenProcess(_OPEN_RIGHTS, False, pid)
        if not h:
            return
        try:
            if pid in self._eco:
                if self._set_eco_handle(h, False):
                    self._eco.discard(pid)
        except Exception:
            pass
        try:
            kernel32.CloseHandle(h)
        except Exception:
            pass

    def _set_eco_handle(self, h, on):
        priority_ok = bool(kernel32.SetPriorityClass(
            h, IDLE_PRIORITY_CLASS if on else NORMAL_PRIORITY_CLASS,
        ))
        st = PROCESS_POWER_THROTTLING_STATE()
        st.Version = 1
        st.ControlMask = PROC_POWER_THROTTLING_EXECUTION_SPEED
        st.StateMask = PROC_POWER_THROTTLING_EXECUTION_SPEED if on else 0
        power_ok = bool(kernel32.SetProcessInformation(
            h, PROC_POWER_THROTTLING, ctypes.byref(st), ctypes.sizeof(st),
        ))
        return priority_ok and power_ok

    def _prune_handles(self, keep: set):
        candidates = (
            set(self._handles)
            | set(self._cpu_jobs)
            | set(self._job_failures)
            | set(self._eco)
        )
        for pid in candidates:
            if pid not in keep:
                self._release_handle(pid)
                self._job_failures.pop(pid, None)

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
        with self._status_lock:
            self._status = snap

    def status(self) -> dict:
        with self._status_lock:
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
        snap["benchmarkActive"] = self._benchmark_active
        if not snap.get("running"):
            snap["tracked"] = snap["live"] = snap["throttled"] = snap["holds"] = 0
            snap["capped"] = 0
            snap["breathing"] = False
            snap["targetPids"] = snap["throttledPids"] = snap["heldPids"] = []
        return snap
