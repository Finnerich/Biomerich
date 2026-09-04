import sys

from . import roblox_logs

IS_WINDOWS = sys.platform == "win32"
ROBLOX_EXE = "robloxplayerbeta.exe"


def fit_client_size(width, height, work_width, work_height, frame=(16, 39), margin=12):
    
    width = max(1, int(width))
    height = max(1, int(height))
    work_width = max(1, int(work_width))
    work_height = max(1, int(work_height))
    frame_width, frame_height = (max(0, int(value)) for value in frame)
    usable_width = max(1, work_width - (2 * int(margin)) - frame_width)
    usable_height = max(1, work_height - (2 * int(margin)) - frame_height)
    factor = min(1.0, usable_width / width, usable_height / height)
    client_width = max(1, round(width * factor))
    client_height = max(1, round(height * factor))
    return {
        "clientWidth": client_width,
        "clientHeight": client_height,
        "outerWidth": client_width + frame_width,
        "outerHeight": client_height + frame_height,
        "fitted": factor < 0.9999,
        "factor": factor,
    }

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
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    HWND_TOP = 0
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_TERMINATE = 0x0001
    ASFW_ANY = 0xFFFFFFFF
    VK_MENU = 0x12
    KEYEVENTF_KEYUP = 0x0002

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
    user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
    user32.AttachThreadInput.restype = wintypes.BOOL
    user32.AllowSetForegroundWindow.argtypes = (wintypes.DWORD,)
    user32.AllowSetForegroundWindow.restype = wintypes.BOOL
    user32.keybd_event.argtypes = (wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_void_p)
    user32.SwitchToThisWindow.argtypes = (wintypes.HWND, wintypes.BOOL)
    user32.SetWindowPos.argtypes = (
        wintypes.HWND, wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.UINT,
    )
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.GetClientRect.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.c_void_p)
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.AdjustWindowRectEx.argtypes = (
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    user32.AdjustWindowRectEx.restype = wintypes.BOOL
    user32.SystemParametersInfoW.argtypes = (
        wintypes.UINT,
        wintypes.UINT,
        ctypes.c_void_p,
        wintypes.UINT,
    )
    user32.SystemParametersInfoW.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.PostMessageW.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = (
        wintypes.HWND,
        EnumWindowsProc,
        wintypes.LPARAM,
    )
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    user32.FindWindowW.restype = wintypes.HWND
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)

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

    def close_pid_gracefully(pid, timeout=3.0):
        
        import time as _time

        if not pid:
            return True
        pid = int(pid)
        wm_close = 0x0010
        hwnd_message = wintypes.HWND(-3)
        posted = set()

        def _post_if_owned(hwnd, _lparam):
            owner_pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
            numeric_hwnd = int(hwnd or 0)
            if owner_pid.value == pid and numeric_hwnd not in posted:
                posted.add(numeric_hwnd)
                user32.PostMessageW(hwnd, wm_close, 0, 0)
            return True

        callback = EnumWindowsProc(_post_if_owned)
        user32.EnumWindows(callback, 0)


        user32.EnumChildWindows(hwnd_message, callback, 0)

        deadline = _time.time() + max(0.0, float(timeout))
        while _time.time() < deadline:
            if not pid_alive(pid):
                return True
            _time.sleep(0.1)
        return terminate_pid(pid, timeout=1.0)

    def refresh_notification_area():
        
        import time as _time

        hwnd = user32.FindWindowW("TopLevelWindowForOverflowXamlIsland", None)
        if not hwnd:
            return False

        rect = _RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        if not user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, 4)
            _time.sleep(0.12)
            user32.GetWindowRect(hwnd, ctypes.byref(rect))

        try:
            wm_mousemove = 0x0200
            width = max(0, rect.right - rect.left)
            height = max(0, rect.bottom - rect.top)
            targets = [int(hwnd)]

            def _remember_child(child, _lparam):
                targets.append(int(child))
                return True

            child_callback = EnumWindowsProc(_remember_child)
            user32.EnumChildWindows(hwnd, child_callback, 0)

            for target in targets:
                for y in range(8, height, 12):
                    for x in range(8, width, 12):
                        lparam = (y << 16) | (x & 0xFFFF)
                        user32.PostMessageW(target, wm_mousemove, 0, lparam)
                _time.sleep(0.02)
        finally:


            user32.ShowWindow(hwnd, 0)
        return True

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
            user32.ShowWindow(hwnd, SW_RESTORE)
            _time.sleep(0.12)
        if _fg_int() == hwnd:
            return True

        try:
            user32.AllowSetForegroundWindow(ASFW_ANY)
        except Exception:
            pass

        this_thread = int(kernel32.GetCurrentThreadId())
        target_thread = int(user32.GetWindowThreadProcessId(hwnd, None) or 0)

        ok = False
        for attempt in range(8):

            cur_fg = _fg_int()
            fg_thread = user32.GetWindowThreadProcessId(cur_fg, None) if cur_fg else 0
            attached_threads = []
            for other_thread in dict.fromkeys((int(fg_thread or 0), target_thread)):
                if other_thread and other_thread != this_thread:
                    if user32.AttachThreadInput(this_thread, other_thread, True):
                        attached_threads.append(other_thread)

            try:
                user32.BringWindowToTop(hwnd)
                user32.SetWindowPos(
                    hwnd, HWND_TOP, 0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
                )
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)
            finally:
                for other_thread in reversed(attached_threads):
                    user32.AttachThreadInput(this_thread, other_thread, False)






            if _fg_int() != hwnd:
                user32.keybd_event(VK_MENU, 0, 0, None)
                try:
                    user32.SetForegroundWindow(hwnd)
                    user32.BringWindowToTop(hwnd)
                finally:
                    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, None)

            if _fg_int() != hwnd:
                try:
                    user32.SwitchToThisWindow(hwnd, True)
                except Exception:
                    pass

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
        if user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        return None

    def resize_roblox_for_calibration(width, height):
        
        windows = roblox_windows()
        if not windows:
            return {"ok": False, "error": "roblox_not_found"}
        handles = {int(hwnd) for hwnd, _pid in windows}
        foreground = foreground_hwnd()
        hwnd = foreground if foreground in handles else int(windows[0][0])

        try:
            requested_width = max(640, min(3840, int(width)))
            requested_height = max(360, min(2160, int(height)))
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_size"}

        work = _RECT()
        if not user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0):
            return {"ok": False, "error": "work_area_failed"}
        work_width = int(work.right - work.left)
        work_height = int(work.bottom - work.top)

        style = int(user32.GetWindowLongW(hwnd, -16))
        extended_style = int(user32.GetWindowLongW(hwnd, -20))
        requested_outer = _RECT(0, 0, requested_width, requested_height)
        if not user32.AdjustWindowRectEx(
            ctypes.byref(requested_outer), style, False, extended_style
        ):
            return {"ok": False, "error": "frame_measure_failed"}
        frame_width = (
            requested_outer.right - requested_outer.left - requested_width
        )
        frame_height = (
            requested_outer.bottom - requested_outer.top - requested_height
        )
        fitted = fit_client_size(
            requested_width,
            requested_height,
            work_width,
            work_height,
            frame=(frame_width, frame_height),
        )
        outer_width = fitted["outerWidth"]
        outer_height = fitted["outerHeight"]
        x = int(work.left + max(0, (work_width - outer_width) // 2))
        y = int(work.top + max(0, (work_height - outer_height) // 2))

        user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetWindowPos(
            hwnd, HWND_TOP, x, y, outer_width, outer_height, SWP_SHOWWINDOW
        ))
        if not ok:
            return {"ok": False, "error": "resize_failed"}

        client = _RECT()
        origin = wintypes.POINT(0, 0)
        user32.GetClientRect(hwnd, ctypes.byref(client))
        user32.ClientToScreen(hwnd, ctypes.byref(origin))
        from . import calibration_presets

        client_width = int(client.right - client.left)
        client_height = int(client.bottom - client.top)
        return {
            "ok": True,
            "hwnd": hwnd,
            "requestedWidth": requested_width,
            "requestedHeight": requested_height,
            "clientWidth": client_width,
            "clientHeight": client_height,
            "outerWidth": outer_width,
            "outerHeight": outer_height,
            "x": x,
            "y": y,
            "clientX": int(origin.x),
            "clientY": int(origin.y),
            "aspectRatio": calibration_presets.aspect_ratio(
                client_width, client_height
            ),
            "fitted": fitted["fitted"],
        }

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

    def close_pid_gracefully(pid, timeout=3.0):
        return True

    def refresh_notification_area():
        return False

    def foreground_hwnd():
        return 0

    def foreground_pid():
        return 0

    def window_rect(hwnd):
        return None

    def normalize_window(hwnd, x=None, y=None, w=None, h=None):
        return False

    def resize_roblox_for_calibration(width, height):
        return {"ok": False, "error": "not_windows"}

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



        entry["online"] = True
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
        if e["pid"] is not None:
            continue
        saved = acc.get("windowBinding")
        if not isinstance(saved, dict):
            continue
        try:
            saved_pid = int(saved.get("pid"))
            saved_start = float(saved.get("startTime"))
        except (TypeError, ValueError):
            acc.pop("windowBinding", None)
            continue
        current_start = proc_start.get(saved_pid)
        if (
            saved_pid in valid_pids
            and saved_pid not in used_pids
            and current_start is not None
            and abs(current_start - saved_start) <= 1.0
        ):
            _bind(e, saved_pid, "persisted")
            e["online"] = True
        else:
            acc.pop("windowBinding", None)

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
        return _log_ctime(log_file) if log_file else None

    remaining = []
    for acc in accounts:
        aid = acc.get("id")
        e = result[aid]
        if e["pid"] is not None:
            continue
        ct = _anchor(acc, e["logFile"])




        if ct is not None and (e["online"] or acc.get("launchTime") is not None):
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




    unbound_ids = [aid for aid, info in result.items() if info["pid"] is None]
    free_pids = [pid for pid in proc_start if pid not in used_pids]
    if len(accounts) == 1 and len(unbound_ids) == 1 and len(free_pids) == 1:
        _bind(result[unbound_ids[0]], free_pids[0], "single-window")

    for aid, info in result.items():
        if info["hwnd"] is not None:
            info["label"] = "Window " + str(hwnd_order.get(info["hwnd"], 0) + 1)
            _BIND_CACHE[aid] = {"pid": info["pid"], "log": info["logFile"]}
            start_time = proc_start.get(info["pid"])
            account = acc_by_id.get(aid)
            if account is not None and start_time is not None:
                binding = {
                    "pid": int(info["pid"]),
                    "startTime": float(start_time),
                }
                if account.get("windowBinding") != binding:
                    account["windowBinding"] = binding
        else:
            _BIND_CACHE.pop(aid, None)
            account = acc_by_id.get(aid)
            if account is not None:
                account.pop("windowBinding", None)

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
