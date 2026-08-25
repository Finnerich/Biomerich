from concurrent.futures import ThreadPoolExecutor
import sys
import time

from . import perf, roblox_logs, win_windows
from .roblox_tray_cleanup import cleanup as tray_cleanup

IS_WINDOWS = sys.platform == "win32"


def _pids():
    try:
        return {int(pid) for pid in perf.roblox_pids() if int(pid) > 0}
    except (OSError, ValueError, TypeError):
        return set()


def _run_for_pids(pids, fn):
    if not pids:
        return
    with ThreadPoolExecutor(max_workers=min(16, len(pids))) as pool:
        futures = [pool.submit(fn, pid) for pid in pids]
        for future in futures:
            try:
                future.result()
            except OSError:
                pass


def close_all_roblox():
    
    if not IS_WINDOWS:
        return {
            "ok": False,
            "error": "unsupported_platform",
            "closedInstances": 0,
            "remainingPids": [],
        }

    tray_cleanup.stop()
    original = _pids()

    _run_for_pids(
        original, lambda pid: win_windows.close_pid_gracefully(pid, timeout=3.0)
    )

    remaining = _pids()
    _run_for_pids(remaining, lambda pid: win_windows.terminate_pid(pid, timeout=2.0))

    deadline = time.monotonic() + 3.0
    remaining = _pids()
    while remaining and time.monotonic() < deadline:
        time.sleep(0.1)
        remaining = _pids()

    try:
        win_windows.refresh_notification_area()
    except OSError:
        pass

    closed_count = len(original - remaining)
    return {
        "ok": not remaining,
        "error": None if not remaining else "roblox_still_running",
        "closedInstances": closed_count,
        "closedInstance": closed_count,
        "remainingPids": sorted(remaining),
    }


def clear_logs():
    closed = close_all_roblox()
    closed_count = closed.get("closedInstances", closed.get("closedInstance", 0))

    if not closed.get("ok", False):
        return {
            **closed,
            "closedInstances": closed_count,
            "closedInstance": closed_count,
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }

    deleted = roblox_logs.clear_all()
    return {
        **deleted,
        "closedInstances": closed_count,
        "closedInstance": closed_count,
        "remainingPids": [],
    }
