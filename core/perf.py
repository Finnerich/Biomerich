import os
import sys
import time

from . import win_windows

IS_WINDOWS = sys.platform == "win32"
ROBLOX_EXE = "robloxplayerbeta.exe"

_prev = {}

_name_cache = {"ts": 0.0, "map": {}}
_NAME_TTL = 5.0

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_SET_QUOTA = 0x0100

    SE_PROFILE_SINGLE_PROCESS_PRIVILEGE = 29
    SYSTEM_MEMORY_LIST_INFORMATION = 0x50
    MEMORY_PURGE_STANDBY_LIST = 4

    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    psapi.EnumProcesses.argtypes = (ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    psapi.EnumProcesses.restype = wintypes.BOOL
    psapi.EmptyWorkingSet.argtypes = (wintypes.HANDLE,)
    psapi.EmptyWorkingSet.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD)
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME))
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    def _open(pid):
        return kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

    def _enum_pids():
        size = 4096
        while True:
            arr = (wintypes.DWORD * size)()
            needed = wintypes.DWORD()
            if not psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(needed)):
                return []
            count = needed.value // ctypes.sizeof(wintypes.DWORD)
            if count < size:
                return [int(arr[i]) for i in range(count)]
            size *= 2

    def _proc_name(handle):
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.split("\\")[-1].lower()
        return ""

    def _proc_mem(handle):
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return int(pmc.WorkingSetSize)
        return 0

    def _proc_time(handle):
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if kernel32.GetProcessTimes(handle, ctypes.byref(c), ctypes.byref(e),
                                    ctypes.byref(k), ctypes.byref(u)):
            kt = (k.dwHighDateTime << 32) | k.dwLowDateTime
            ut = (u.dwHighDateTime << 32) | u.dwLowDateTime
            return kt + ut
        return None

    def _total_ram():
        msx = MEMORYSTATUSEX()
        msx.dwLength = ctypes.sizeof(msx)
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(msx)):
            return int(msx.ullTotalPhys)
        return 0

    def roblox_pids():
        out = []
        for pid in _enum_pids():
            if pid <= 0:
                continue
            h = _open(pid)
            if not h:
                continue
            try:
                if _proc_name(h) == ROBLOX_EXE:
                    out.append(pid)
            finally:
                kernel32.CloseHandle(h)
        return out

    def _measure(pid, now, ncores):
        h = _open(pid)
        if not h:
            return None
        try:
            ram = _proc_mem(h)
            ptime = _proc_time(h)
        finally:
            kernel32.CloseHandle(h)
        cpu = 0.0
        prev = _prev.get(pid)
        if prev and ptime is not None:
            dt = now - prev[1]
            dp = ptime - prev[0]
            if dt > 0 and dp >= 0:
                cpu = (dp * 1e-7) / dt / max(1, ncores) * 100.0
        if ptime is not None:
            _prev[pid] = (ptime, now)
        return {"ramBytes": ram, "cpuPercent": round(min(cpu, 100.0), 1)}

    def _avail_ram():
        msx = MEMORYSTATUSEX()
        msx.dwLength = ctypes.sizeof(msx)
        if kernel32.GlobalMemoryStatusEx(ctypes.byref(msx)):
            return int(msx.ullAvailPhys)
        return 0

    def _purge_standby_list():
        
        try:
            enabled = ctypes.c_byte(0)
            ntdll.RtlAdjustPrivilege(SE_PROFILE_SINGLE_PROCESS_PRIVILEGE, 1, 0, ctypes.byref(enabled))
            command = ctypes.c_int(MEMORY_PURGE_STANDBY_LIST)
            status = ntdll.NtSetSystemInformation(
                SYSTEM_MEMORY_LIST_INFORMATION, ctypes.byref(command), ctypes.sizeof(command))
            return int(status) == 0
        except Exception as e:
            print(f"[Perf] Standby purge failed: {e}")
            return False

    QUOTA_LIMITS_HARDWS_MIN_DISABLE = 0x00000002
    QUOTA_LIMITS_HARDWS_MAX_ENABLE = 0x00000004
    QUOTA_LIMITS_HARDWS_MAX_DISABLE = 0x00000008

    kernel32.SetProcessWorkingSetSizeEx.argtypes = (
        wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD)
    kernel32.SetProcessWorkingSetSizeEx.restype = wintypes.BOOL

    def cap_working_set(pids, max_bytes):
        
        max_bytes = max(64 * 1048576, int(max_bytes))
        min_bytes = min(32 * 1048576, max_bytes // 2)
        flags = QUOTA_LIMITS_HARDWS_MAX_ENABLE | QUOTA_LIMITS_HARDWS_MIN_DISABLE
        count = 0
        for pid in (pids or []):
            h = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, int(pid))
            if not h:
                continue
            try:
                if kernel32.SetProcessWorkingSetSizeEx(h, min_bytes, max_bytes, flags):
                    count += 1
            finally:
                kernel32.CloseHandle(h)
        return count

    def uncap_working_set(pids):
        
        flags = QUOTA_LIMITS_HARDWS_MAX_DISABLE | QUOTA_LIMITS_HARDWS_MIN_DISABLE
        count = 0
        for pid in (pids or []):
            h = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, int(pid))
            if not h:
                continue
            try:
                if kernel32.SetProcessWorkingSetSizeEx(h, 32 * 1048576, 1536 * 1048576, flags):
                    count += 1
            finally:
                kernel32.CloseHandle(h)
        return count

    def trim_system_ram():
        avail_before = _avail_ram()

        trimmed = 0
        for pid in _enum_pids():
            if pid <= 4:
                continue
            h = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid)
            if not h:
                continue
            try:
                if psapi.EmptyWorkingSet(h):
                    trimmed += 1
            finally:
                kernel32.CloseHandle(h)

        purged = _purge_standby_list()

        time.sleep(0.12)
        avail_after = _avail_ram()
        freed = max(0, avail_after - avail_before)

        print(f"[Perf] System trim: {trimmed} process(es), "
              f"standby purge={'yes' if purged else 'no (needs admin)'}, "
              f"freed {freed / 1048576:.0f} MB.")
        return {
            "ok": True,
            "count": trimmed,
            "freedBytes": freed,
            "availBefore": avail_before,
            "availAfter": avail_after,
            "standbyPurged": purged,
        }

else:
    def roblox_pids():
        return []

    def _measure(pid, now, ncores):
        return None

    def _total_ram():
        return 0

    def cap_working_set(pids, max_bytes):
        return 0

    def uncap_working_set(pids):
        return 0

    def trim_system_ram():
        return {"ok": False, "error": "not_windows"}


def process_counters(pids):
    
    if not IS_WINDOWS:
        return {}
    counters = {}
    for raw_pid in pids or []:
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            continue
        handle = _open(pid)
        if not handle:
            continue
        try:
            cpu_time = _proc_time(handle)
            if cpu_time is None:
                continue
            counters[pid] = {
                "ramBytes": _proc_mem(handle),
                "cpuTime100ns": int(cpu_time),
            }
        finally:
            kernel32.CloseHandle(handle)
    return counters

def snapshot(accounts):
    ncores = os.cpu_count() or 1
    now = time.perf_counter()
    macro_pid = os.getpid()

    pids = roblox_pids() if IS_WINDOWS else []

    pid_to_name = {}
    if IS_WINDOWS:
        stale = (now - _name_cache["ts"]) > _NAME_TTL
        unknown = any(p not in _name_cache["map"] for p in pids)
        if stale or unknown:
            try:
                resolved = win_windows.resolve_accounts(accounts or [])
                id_to_name = {a.get("id"): a.get("name", "?") for a in (accounts or [])}
                fresh = {}
                for acc_id, info in resolved.items():
                    pid = info.get("pid")
                    if pid:
                        fresh[pid] = id_to_name.get(acc_id, "?")
                _name_cache["map"] = fresh
                _name_cache["ts"] = now
            except Exception:
                pass
        pid_to_name = _name_cache["map"]

    instances = []
    total_ram = 0
    total_cpu = 0.0
    seen = set()
    unnamed = 0
    for pid in pids:
        m = _measure(pid, now, ncores)
        if not m:
            continue
        seen.add(pid)
        name = pid_to_name.get(pid)
        if not name:
            unnamed += 1
            name = f"Roblox #{unnamed}"
        instances.append({
            "pid": pid, "name": name,
            "ramBytes": m["ramBytes"], "cpuPercent": m["cpuPercent"],
        })
        total_ram += m["ramBytes"]
        total_cpu += m["cpuPercent"]

    instances.sort(key=lambda x: x["pid"])

    macro = {"pid": macro_pid, "name": "SolRich", "ramBytes": 0, "cpuPercent": 0.0}
    mm = _measure(macro_pid, now, ncores) if IS_WINDOWS else None
    if mm:
        macro["ramBytes"] = mm["ramBytes"]
        macro["cpuPercent"] = mm["cpuPercent"]

    seen.add(macro_pid)
    for stale in [p for p in _prev if p not in seen]:
        _prev.pop(stale, None)

    return {
        "supported": IS_WINDOWS,
        "ncores": ncores,
        "totalRamBytes": _total_ram(),
        "instances": instances,
        "robloxTotal": {
            "count": len(instances),
            "ramBytes": total_ram,
            "cpuPercent": round(min(total_cpu, 100.0), 1),
        },
        "macro": macro,
    }
