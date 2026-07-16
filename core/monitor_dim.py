

import sys
import threading
import time

IS_WINDOWS = sys.platform == "win32"

FADE_SECS = 0.4
_CLASS_NAME = "SolRichMonitorDim"

_lock = threading.Lock()
_thread = None
_target = 0
_stop = False

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    WS_POPUP = 0x80000000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    WS_EX_TOPMOST = 0x00000008
    LWA_ALPHA = 0x00000002
    SW_SHOWNOACTIVATE = 4
    WDA_EXCLUDEFROMCAPTURE = 0x00000011
    BLACK_BRUSH = 4
    PM_REMOVE = 0x0001

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
            ("hCursor", ctypes.c_void_p), ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
        ]

    user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.SetLayeredWindowAttributes.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD)
    user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL

    _wndproc = WNDPROC(lambda h, m, w, l: user32.DefWindowProcW(h, m, w, l))
    _class_registered = False

    def _monitor_rects():
        rects = []

        def cb(hmon, hdc, rect, lparam):
            r = rect.contents
            rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
            return True

        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
        return rects or [(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))]

    def _create_windows():
        global _class_registered
        if not _class_registered:
            wc = WNDCLASSW()
            wc.lpfnWndProc = _wndproc
            wc.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
            wc.lpszClassName = _CLASS_NAME
            if not user32.RegisterClassW(ctypes.byref(wc)):

                if ctypes.get_last_error() != 1410:
                    return None
            _class_registered = True

        ex = (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
              | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        hwnds = []
        for x, y, w, h in _monitor_rects():
            hwnd = user32.CreateWindowExW(ex, _CLASS_NAME, None, WS_POPUP,
                                          x, y, w, h, None, None, None, None)
            if not hwnd:
                continue
            user32.SetLayeredWindowAttributes(hwnd, 0, 0, LWA_ALPHA)
            if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):


                for hw in hwnds + [hwnd]:
                    user32.DestroyWindow(hw)
                print("[MonitorDim] WDA_EXCLUDEFROMCAPTURE unavailable; dimming disabled.")
                return None
            user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
            hwnds.append(hwnd)
        return hwnds or None

    def _worker():
        global _thread
        hwnds = _create_windows()
        if hwnds is None:
            with _lock:
                _thread = None
            return
        alpha = 0.0
        msg = wintypes.MSG()
        try:
            while True:
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                with _lock:
                    target = 0 if _stop else _target
                    done = _stop and alpha <= 0.5
                if done:
                    break
                if alpha != target:
                    step = 255.0 / (FADE_SECS / 0.016)
                    alpha = min(alpha + step, target) if alpha < target else max(alpha - step, target)
                    for hw in hwnds:
                        user32.SetLayeredWindowAttributes(hw, 0, int(alpha), LWA_ALPHA)
                time.sleep(0.016)
        finally:
            for hw in hwnds:
                user32.DestroyWindow(hw)
            with _lock:
                _thread = None


def _alpha_for(level_pct) -> int:
    try:
        level = max(0, min(80, int(level_pct)))
    except (TypeError, ValueError):
        level = 40
    return int(level * 255 / 100)


def start(level_pct):
    
    global _thread, _target, _stop
    if not IS_WINDOWS:
        return
    with _lock:
        _target = _alpha_for(level_pct)
        _stop = False
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(target=_worker, daemon=True, name="MonitorDim")
            _thread.start()


def stop():
    
    global _stop
    with _lock:
        _stop = True
