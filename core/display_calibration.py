

from __future__ import annotations

import re
import sys
from typing import Iterable, Optional

from . import calibration_presets


_PRESET_RE = re.compile(
    r"^\[[^\]]+\]\s+(WINDOWED|FULLSCREEN)\s+(\d+)\s*[x×]\s*(\d+)\s+\((\d+)%\)\s*$",
    re.IGNORECASE,
)


def parse_preset_name(name: str) -> Optional[dict]:
    
    match = _PRESET_RE.match(str(name or "").strip())
    if not match:
        return None
    mode, width, height, scale = match.groups()
    return {
        "name": str(name),
        "mode": mode.upper(),
        "width": int(width),
        "height": int(height),
        "scale": int(scale),
    }


def _preset_entries(presets):
    entries = []
    for item in presets:
        raw = item if isinstance(item, dict) else {"name": item}
        parsed = parse_preset_name(raw.get("name"))
        if not parsed:
            continue
        entries.append(parsed)
    return entries


def recommend_preset_details(presets: Iterable, target: Optional[dict]) -> Optional[dict]:
    
    if not target:
        return None
    target_width = int(target.get("width") or 0)
    target_height = int(target.get("height") or 0)
    target_scale = int(target.get("scale") or 0)
    target_mode = str(target.get("mode") or "").upper()
    entries = _preset_entries(presets)

    wanted = (target_width, target_height, target_scale, target_mode)
    for entry in entries:
        signature = (
            entry["width"], entry["height"], entry["scale"], entry["mode"]
        )
        if signature == wanted:
            return {
                "name": entry["name"],
                "strategy": "absolute",
                "sourceWidth": entry["width"],
                "sourceHeight": entry["height"],
                "targetWidth": target_width,
                "targetHeight": target_height,
                "aspectRatio": calibration_presets.aspect_ratio(
                    target_width, target_height
                ),
                "scaled": False,
            }
    return None


def recommend_preset(preset_names: Iterable[str], target: Optional[dict]) -> Optional[str]:
    
    match = recommend_preset_details(preset_names, target)
    return match["name"] if match else None


def _unsupported(error: str = "unsupported") -> dict:
    return {
        "ok": False,
        "error": error,
        "monitors": [],
        "target": None,
        "preset": None,
        "match": None,
        "reason": "unsupported",
    }


def inspect_displays(preset_names: Iterable[str]) -> dict:
    
    if sys.platform != "win32":
        return _unsupported()

    try:
        monitors, targets = _read_windows_displays()
    except Exception as error:
        return _unsupported(str(error) or "display_detection_failed")

    if not monitors:
        return _unsupported("no_displays")

    reason = None
    target = None
    if targets:
        signatures = {
            (item["width"], item["height"], item["scale"], item["mode"])
            for item in targets
        }
        if len(signatures) == 1:
            target = dict(targets[0])
            target["source"] = "roblox"
            target["robloxWindows"] = len(targets)
        else:
            reason = "mixed_displays"
    else:
        primary = next((item for item in monitors if item["primary"]), monitors[0])
        target = {
            "displayId": primary["id"],
            "device": primary["device"],
            "x": primary["x"],
            "y": primary["y"],
            "width": primary["width"],
            "height": primary["height"],
            "scale": primary["scale"],
            "mode": "WINDOWED",
            "source": "primary",
            "robloxWindows": 0,
        }

    if target:
        target["aspectRatio"] = calibration_presets.aspect_ratio(
            target["width"], target["height"]
        )
    match = recommend_preset_details(preset_names, target)
    preset = match["name"] if match else None
    if target and not preset:
        reason = "no_preset"

    return {
        "ok": True,
        "error": None,
        "monitors": monitors,
        "target": target,
        "preset": preset,
        "match": match,
        "reason": reason,
    }


def _read_windows_displays():
    
    import ctypes
    from ctypes import wintypes

    from . import win_windows

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
    except OSError:
        shcore = None

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG), ("top", wintypes.LONG),
            ("right", wintypes.LONG), ("bottom", wintypes.LONG),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    monitor_handle = wintypes.HANDLE
    enum_proc_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        monitor_handle,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )
    user32.EnumDisplayMonitors.argtypes = (
        wintypes.HDC, ctypes.POINTER(RECT), enum_proc_type, wintypes.LPARAM,
    )
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    user32.GetMonitorInfoW.argtypes = (monitor_handle, ctypes.POINTER(MONITORINFOEXW))
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.MonitorFromWindow.restype = monitor_handle
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowLongW.restype = ctypes.c_long

    if shcore is not None:
        shcore.GetDpiForMonitor.argtypes = (
            monitor_handle,
            ctypes.c_int,
            ctypes.POINTER(wintypes.UINT),
            ctypes.POINTER(wintypes.UINT),
        )
        shcore.GetDpiForMonitor.restype = ctypes.c_long

    def handle_value(handle) -> int:
        return int(ctypes.cast(handle, ctypes.c_void_p).value or 0)

    def monitor_scale(handle) -> tuple[int, int]:
        dpi = 96
        if shcore is not None:
            x_dpi, y_dpi = wintypes.UINT(96), wintypes.UINT(96)
            if shcore.GetDpiForMonitor(handle, 0, ctypes.byref(x_dpi), ctypes.byref(y_dpi)) == 0:
                dpi = int(x_dpi.value or 96)
        return dpi, max(100, int(round((dpi / 96.0) * 100)))

    raw_monitors = []

    def collect(handle, _hdc, _rect, _lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return True
        dpi, scale = monitor_scale(handle)
        rect, work = info.rcMonitor, info.rcWork
        raw_monitors.append({
            "handle": handle_value(handle),
            "device": str(info.szDevice),
            "x": int(rect.left),
            "y": int(rect.top),
            "width": int(rect.right - rect.left),
            "height": int(rect.bottom - rect.top),
            "aspectRatio": calibration_presets.aspect_ratio(
                int(rect.right - rect.left), int(rect.bottom - rect.top)
            ),
            "workWidth": int(work.right - work.left),
            "workHeight": int(work.bottom - work.top),
            "dpi": dpi,
            "scale": scale,
            "primary": bool(info.dwFlags & 1),
            "robloxWindows": 0,
        })
        return True

    callback = enum_proc_type(collect)
    if not user32.EnumDisplayMonitors(None, None, callback, 0):
        raise OSError(ctypes.get_last_error(), "EnumDisplayMonitors failed")

    raw_monitors.sort(key=lambda item: (not item["primary"], item["x"], item["y"]))
    for index, item in enumerate(raw_monitors, 1):
        item["id"] = index

    by_handle = {item["handle"]: item for item in raw_monitors}
    targets = []
    ws_caption = 0x00C00000
    monitor_default_to_nearest = 2
    for hwnd, _pid in win_windows.roblox_windows():
        handle = user32.MonitorFromWindow(wintypes.HWND(int(hwnd)), monitor_default_to_nearest)
        monitor = by_handle.get(handle_value(handle))
        if not monitor:
            continue
        monitor["robloxWindows"] += 1
        style = int(user32.GetWindowLongW(wintypes.HWND(int(hwnd)), -16))
        mode = "WINDOWED" if style & ws_caption else "FULLSCREEN"
        targets.append({
            "displayId": monitor["id"],
            "device": monitor["device"],
            "x": monitor["x"],
            "y": monitor["y"],
            "width": monitor["width"],
            "height": monitor["height"],
            "scale": monitor["scale"],
            "mode": mode,
        })

    monitors = [{key: value for key, value in item.items() if key != "handle"} for item in raw_monitors]
    return monitors, targets
