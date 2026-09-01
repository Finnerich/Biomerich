

from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
from ctypes import wintypes


_NOTIFICATIONS = queue.Queue(maxsize=32)
_WORKER_LOCK = threading.Lock()
_WORKER = None


def _clean(value, limit):
    return " ".join(str(value or "").split())[:limit]


def notify(title, message, *, kind="info", seconds=6) -> bool:
    
    if sys.platform != "win32":
        return False
    item = (
        _clean(title, 63) or "SolRich",
        _clean(message, 255),
        str(kind or "info").casefold(),
        max(3, min(12, int(seconds or 6))),
    )
    try:
        _NOTIFICATIONS.put_nowait(item)
    except queue.Full:
        print("[Notifications] Queue full; skipped a Windows notification.")
        return False
    _ensure_worker()
    return True


def _ensure_worker():
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is not None and _WORKER.is_alive():
            return
        _WORKER = threading.Thread(
            target=_worker,
            name="windows-notifications",
            daemon=True,
        )
        _WORKER.start()


def _worker():
    while True:
        title, message, kind, seconds = _NOTIFICATIONS.get()
        try:
            _show_balloon(title, message, kind, seconds)
        except Exception as exc:
            print(f"[Notifications] Windows notification failed: {exc}")
        finally:
            _NOTIFICATIONS.task_done()


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", _GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


def _show_balloon(title, message, kind, seconds):
    user32 = ctypes.windll.user32
    shell32 = ctypes.windll.shell32

    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
    )
    window = user32.CreateWindowExW(
        0, "STATIC", "SolRich Notifications", 0,
        0, 0, 0, 0, None, None, None, None,
    )
    if not window:
        raise ctypes.WinError()

    large_icon = wintypes.HICON()
    small_icon = wintypes.HICON()
    extracted = shell32.ExtractIconExW(
        os.path.abspath(sys.executable), 0,
        ctypes.byref(large_icon), ctypes.byref(small_icon), 1,
    )
    icon = small_icon.value or large_icon.value
    if not icon:
        icon = user32.LoadIconW(None, 32512)

    NIM_ADD = 0
    NIM_MODIFY = 1
    NIM_DELETE = 2
    NIF_ICON = 0x2
    NIF_TIP = 0x4
    NIF_INFO = 0x10
    info_flags = {
        "error": 0x3,
        "warning": 0x2,
        "success": 0x1,
        "info": 0x1,
    }.get(kind, 0x1)

    data = _NOTIFYICONDATAW()
    data.cbSize = ctypes.sizeof(data)
    data.hWnd = window
    data.uID = 1
    data.uFlags = NIF_ICON | NIF_TIP
    data.hIcon = icon
    data.szTip = "SolRich"

    try:
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(data)):
            raise ctypes.WinError()
        data.uFlags = NIF_INFO
        data.szInfoTitle = title
        data.szInfo = message
        data.dwInfoFlags = info_flags
        data.uTimeoutOrVersion = seconds * 1000
        if not shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(data)):
            raise ctypes.WinError()

        threading.Event().wait(seconds)
    finally:
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
        if extracted:
            if small_icon.value:
                user32.DestroyIcon(small_icon)
            if large_icon.value and large_icon.value != small_icon.value:
                user32.DestroyIcon(large_icon)
        user32.DestroyWindow(window)
