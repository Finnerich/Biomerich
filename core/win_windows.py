import sys

from . import roblox_logs

IS_WINDOWS = sys.platform == "win32"
ROBLOX_EXE = "robloxplayerbeta.exe"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    rstrtmgr = ctypes.WinDLL("rstrtmgr", use_last_error=True)

    SW_RESTORE = 9
    SW_SHOWNORMAL = 1
    SW_SHOW = 5
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    HWND_TOP = 0
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_TERMINATE = 0x0001
    ASFW_ANY = 0xFFFFFFFF

    CCH_RM_SESSION_KEY = 32
    CCH_RM_MAX_APP_NAME = 255
    CCH_RM_MAX_SVC_NAME = 63
    RM_REBOOT_REASON_NONE = 0

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class RM_UNIQUE_PROCESS(ctypes.Structure):
        _fields_ = [("dwProcessId", wintypes.DWORD), ("ProcessStartTime", FILETIME)]

    class RM_PROCESS_INFO(ctypes.Structure):
        _fields_ = [
            ("Process", RM_UNIQUE_PROCESS),
            ("strAppName", wintypes.WCHAR * (CCH_RM_MAX_APP_NAME + 1)),
            ("strServiceShortName", wintypes.WCHAR * (CCH_RM_MAX_SVC_NAME + 1)),
            ("ApplicationType", ctypes.c_int),
            ("AppStatus", wintypes.ULONG),
            ("TSSessionId", wintypes.DWORD),
            ("bRestartable", wintypes.BOOL),
        ]

    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD,
        wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    user32.EnumWindows.argtypes = (EnumWindowsProc, wintypes.LPARAM)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = (wintypes.HWND,)
    user32.IsIconic.argtypes = (wintypes.HWND,)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.SetActiveWindow.argtypes = (wintypes.HWND,)
    user32.SetActiveWindow.restype = wintypes.HWND
    user32.SetFocus.argtypes = (wintypes.HWND,)
    user32.SetFocus.restype = wintypes.HWND
    user32.SetWindowPos.argtypes = (
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    )
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.GetWindowRect.restype = wintypes.BOOL

    GA_ROOT = 2
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND

    def hwnd_from_click(timeout=30.0, cancel_flag=None):

        import time as _time
        from . import win_input

        pos = win_input.capture_next_click(timeout=timeout,
                                           should_cancel=cancel_flag)
        if not pos:
            return None, None
        pt = wintypes.POINT(int(pos[0]), int(pos[1]))
        child = user32.WindowFromPoint(pt)
        if not child:
            return None, None
        root = user32.GetAncestor(child, GA_ROOT)
        hwnd = int(root or child)
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        p = pid.value
        if _process_name(p) != ROBLOX_EXE:
            return None, None
        return hwnd, p

    def _process_name(pid):
        if not pid:
            return ""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return buf.value.split("\\")[-1].lower()
        finally:
            kernel32.CloseHandle(handle)
        return ""

    def pid_alive(pid):
        return bool(pid) and _process_name(int(pid)) == ROBLOX_EXE

    def terminate_pid(pid, timeout=4.0):

        import time as _time
        if not pid:
            return True
        pid = int(pid)
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            try:
                kernel32.TerminateProcess(handle, 0)
            finally:
                kernel32.CloseHandle(handle)
        deadline = _time.time() + timeout
        while _time.time() < deadline:
            if _process_name(pid) != ROBLOX_EXE:
                return True
            _time.sleep(0.1)
        return _process_name(pid) != ROBLOX_EXE

    def _process_start_time(pid):

        if not pid:
            return None
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            creation = FILETIME()
            exit_t   = FILETIME()
            kernel_t = FILETIME()
            user_t   = FILETIME()
            ok = kernel32.GetProcessTimes(
                handle,
                ctypes.byref(creation),
                ctypes.byref(exit_t),
                ctypes.byref(kernel_t),
                ctypes.byref(user_t),
            )
            if not ok:
                return None

            ft = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            EPOCH_DIFF = 116444736000000000
            return (ft - EPOCH_DIFF) / 10_000_000.0
        finally:
            kernel32.CloseHandle(handle)

    def _window_title(hwnd):
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def roblox_windows():

        by_pid = {}

        def _cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            p = pid.value
            if not p or _process_name(p) != ROBLOX_EXE:
                return True
            title = _window_title(hwnd)
            prev = by_pid.get(p)

            if prev is None:
                by_pid[p] = (int(hwnd), bool(title))
            elif title and not prev[1]:
                by_pid[p] = (int(hwnd), True)
            return True

        user32.EnumWindows(EnumWindowsProc(_cb), 0)

        return [(h, p) for p, (h, _t) in by_pid.items()]

    def pid_holding_file(path):
        pids = log_lock_pids(path)
        return pids[0] if pids else None

    def log_lock_pids(path):

        if not path:
            return []
        session = wintypes.DWORD(0)
        key = ctypes.create_unicode_buffer(CCH_RM_SESSION_KEY + 1)
        if rstrtmgr.RmStartSession(ctypes.byref(session), 0, key) != 0:
            return []
        try:
            resources = (wintypes.LPCWSTR * 1)(path)
            if rstrtmgr.RmRegisterResources(session, 1, resources, 0, None, 0, None) != 0:
                return []
            needed = wintypes.UINT(0)
            count = wintypes.UINT(0)
            reasons = wintypes.DWORD(0)
            rstrtmgr.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), None, ctypes.byref(reasons))
            if needed.value == 0:
                return []
            arr = (RM_PROCESS_INFO * needed.value)()
            count = wintypes.UINT(needed.value)
            if rstrtmgr.RmGetList(session, ctypes.byref(needed), ctypes.byref(count), arr, ctypes.byref(reasons)) != 0:
                return []
            out = []
            for i in range(count.value):
                pid = int(arr[i].Process.dwProcessId)
                if _process_name(pid) == ROBLOX_EXE:
                    out.append(pid)
            return out
        except Exception:
            return []
        finally:
            rstrtmgr.RmEndSession(session)

    NORMALIZE_X = 0
    NORMALIZE_Y = 0
    NORMALIZE_W = 1936
    NORMALIZE_H = 1048

    def normalize_window(hwnd, x=None, y=None, w=None, h=None):

        if not hwnd:
            return False
        import time as _time
        hwnd = int(hwnd)
        x = NORMALIZE_X if x is None else x
        y = NORMALIZE_Y if y is None else y
        w = NORMALIZE_W if w is None else w
        h = NORMALIZE_H if h is None else h
        try:
            user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        except Exception:
            pass
        _time.sleep(0.05)

        flags = SWP_SHOWWINDOW
        ok = bool(user32.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(w), int(h), flags))
        _time.sleep(0.05)

        user32.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(w), int(h), flags)
        return ok

    def _fg_int():

        h = user32.GetForegroundWindow()
        try:
            return int(h or 0)
        except (TypeError, ValueError):
            return int(ctypes.cast(h, ctypes.c_void_p).value or 0)

    def focus_hwnd(hwnd):
        import time as _time
        if not hwnd:
            return False
        hwnd = int(hwnd)

        if user32.IsIconic(hwnd):

            user32.ShowWindow(hwnd, SW_SHOW)
            _time.sleep(0.12)
        if _fg_int() == hwnd:
            return True

        try:
            user32.AllowSetForegroundWindow(ASFW_ANY)
        except Exception:
            pass

        this_thread = kernel32.GetCurrentThreadId()

        ok = False
        for attempt in range(8):

            cur_fg = _fg_int()
            fg_thread = user32.GetWindowThreadProcessId(cur_fg, None) if cur_fg else 0
            attached = False
            if fg_thread and fg_thread != this_thread:
                attached = bool(user32.AttachThreadInput(fg_thread, this_thread, True))

            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetActiveWindow(hwnd)
            user32.SetFocus(hwnd)

            if attached:
                user32.AttachThreadInput(fg_thread, this_thread, False)

            _time.sleep(0.12)
            if _fg_int() == hwnd:
                ok = True
                break

        _time.sleep(0.25)

        return _fg_int() == hwnd

    def foreground_hwnd():
        return int(user32.GetForegroundWindow() or 0)

    def foreground_pid():
        h = user32.GetForegroundWindow()
        if not h:
            return 0
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        return int(pid.value)

    class _RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    def window_rect(hwnd):

        if not hwnd:
            return None
        r = _RECT()
        user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(_RECT))
        if user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        return None

else:
    def roblox_windows():
        return []

    def pid_holding_file(path):
        return None

    def log_lock_pids(path):
        return []

    def focus_hwnd(hwnd):
        return False

    def _process_start_time(pid):
        return None

    def pid_alive(pid):
        return False

    def terminate_pid(pid, timeout=4.0):
        return True

    def foreground_hwnd():
        return 0

    def foreground_pid():
        return 0

    def window_rect(hwnd):
        return None

    def normalize_window(hwnd, x=None, y=None, w=None, h=None):
        return False

    def hwnd_from_click(timeout=30.0, cancel_flag=None):
        return None, None

_BIND_CACHE = {}
_MANUAL_BIND = {}

def set_manual_bind(acc_id, hwnd, pid):

    _MANUAL_BIND[acc_id] = {"hwnd": int(hwnd), "pid": int(pid)}

    _BIND_CACHE[acc_id] = {"pid": int(pid), "log": None}

def clear_manual_bind(acc_id):
    _MANUAL_BIND.pop(acc_id, None)
    _BIND_CACHE.pop(acc_id, None)

def resolve_accounts(accounts):

    import os as _os
    import itertools as _it

    result = {}
    if not accounts:
        return result

    names = [a.get("name", "") for a in accounts if a.get("name")]
    log_map = roblox_logs.match_logs_to_usernames(names)
    windows = roblox_windows()
    hwnd_order = {hwnd: i for i, (hwnd, _pid) in enumerate(windows)}
    pid_to_hwnd = {pid: hwnd for hwnd, pid in windows}
    valid_pids = set(pid_to_hwnd)

    proc_start = {}
    for _hwnd, pid in windows:
        st = _process_start_time(pid)
        if st is not None:
            proc_start[pid] = st

    def _log_ctime(path):
        try:
            return _os.path.getctime(path)
        except OSError:
            try:
                return _os.path.getmtime(path)
            except OSError:
                return None

    used_pids = set()

    def _bind(entry, pid, via):
        entry["pid"] = pid
        entry["hwnd"] = pid_to_hwnd.get(pid)
        entry["via"] = via
        used_pids.add(pid)

    for acc in accounts:
        uname = (acc.get("name") or "").strip().lower()
        log_file = log_map.get(uname)
        result[acc.get("id")] = {
            "hwnd": None, "pid": None,
            "online": log_file is not None,
            "label": None, "logFile": log_file, "via": None,
        }

    for acc in accounts:
        aid = acc.get("id")
        e = result[aid]
        m = _MANUAL_BIND.get(aid)
        if not m:
            continue
        mpid = m["pid"]
        mhwnd = m["hwnd"]
        if mpid not in valid_pids:

            _MANUAL_BIND.pop(aid, None)
            _BIND_CACHE.pop(aid, None)
            continue
        if mpid in used_pids:
            continue
        e["pid"] = mpid
        e["hwnd"] = mhwnd
        e["via"] = "manual"
        e["online"] = True
        used_pids.add(mpid)

    for acc in accounts:
        aid = acc.get("id")
        e = result[aid]
        c = _BIND_CACHE.get(aid)
        if (e["logFile"] and c and c.get("log") == e["logFile"]
                and c.get("pid") in valid_pids and c.get("pid") not in used_pids):
            _bind(e, c["pid"], "cache")

    for acc in accounts:
        aid = acc.get("id")
        e = result[aid]
        if e["pid"] is not None or not e["logFile"]:
            continue
        owners = [p for p in log_lock_pids(e["logFile"])
                  if p in valid_pids and p not in used_pids]
        if len(owners) == 1:
            _bind(e, owners[0], "file-lock")
        elif len(owners) > 1:
            owners.sort(key=lambda p: proc_start.get(p, 0))
            _bind(e, owners[0], "file-lock")

    def _anchor(acc, log_file):
        lt = acc.get("launchTime")
        if lt:
            return float(lt)
        return _log_ctime(log_file)

    remaining = []
    for acc in accounts:
        aid = acc.get("id")
        e = result[aid]
        if e["pid"] is not None or not e["online"]:
            continue
        ct = _anchor(acc, e["logFile"])
        if ct is not None:
            remaining.append((aid, ct))

    acc_by_id = {a.get("id"): a for a in accounts}

    free_pids = [p for p in proc_start if p not in used_pids]

    if remaining and free_pids:

        TOLERANCE = 180
        if len(remaining) <= 6 and len(free_pids) <= 6:
            best_combo, best_cost = None, None
            k = min(len(remaining), len(free_pids))
            for accs in _it.permutations(remaining, k):
                for pids in _it.permutations(free_pids, k):
                    cost, ok = 0.0, True
                    for (aid, ct), pid in zip(accs, pids):
                        d = abs(proc_start[pid] - ct)
                        if d > TOLERANCE:
                            ok = False
                            break
                        cost += d
                    if ok and (best_cost is None or cost < best_cost):
                        best_combo, best_cost = list(zip(accs, pids)), cost
            if best_combo:
                for (aid, _ct), pid in best_combo:
                    _bind(result[aid], pid, "time")
        else:
            pairs = sorted(
                ((abs(proc_start[pid] - ct), aid, pid)
                 for aid, ct in remaining for pid in free_pids
                 if abs(proc_start[pid] - ct) <= TOLERANCE),
                key=lambda t: t[0],
            )
            taken_acc = set()
            for _d, aid, pid in pairs:
                if aid in taken_acc or pid in used_pids:
                    continue
                _bind(result[aid], pid, "time")
                taken_acc.add(aid)

    unmatched = [aid for aid, info in result.items()
                 if info["pid"] is None and info["online"]]
    leftover_pids = [p for p in proc_start if p not in used_pids]
    if unmatched and len(unmatched) == len(leftover_pids):
        leftover_pids.sort(key=lambda p: proc_start[p])
        unmatched.sort(key=lambda aid: _anchor(acc_by_id[aid], result[aid]["logFile"]) or 0)
        for aid, pid in zip(unmatched, leftover_pids):
            _bind(result[aid], pid, "count")

    for aid, info in result.items():
        if info["hwnd"] is not None:
            info["label"] = "Window " + str(hwnd_order.get(info["hwnd"], 0) + 1)
            _BIND_CACHE[aid] = {"pid": info["pid"], "log": info["logFile"]}
        else:
            _BIND_CACHE.pop(aid, None)

    still = []
    for acc in accounts:
        aid = acc.get("id")
        info = result.get(aid, {})
        if info.get("hwnd") is None:
            uname = (acc.get("name") or "").strip()
            state = "online, unmatched" if info.get("online") else "no log"
            still.append(f"{uname}({state})")
    if still:
        print(f"[Windows] Unmatched: {', '.join(still)} | "
              f"{len(windows)} Roblox windows, {len(proc_start)} with start-time")

    return result
