

from __future__ import annotations

import queue
import sys
import threading
import time
from dataclasses import dataclass


IS_WINDOWS = sys.platform == "win32"
WINDOW_WIDTH = 125
WINDOW_HEIGHT = 125


SAMPLE_SIZE = 25
CURSOR_GAP = 14
CENTER_DOT_OUTER_RADIUS = 5
CENTER_DOT_INNER_RADIUS = 2


def place_near_cursor(cursor, monitor_rect, window_size=(WINDOW_WIDTH, WINDOW_HEIGHT)):
    
    cursor_x, cursor_y = (int(value) for value in cursor)
    left, top, right, bottom = (int(value) for value in monitor_rect)
    width, height = (int(value) for value in window_size)
    x = cursor_x + CURSOR_GAP
    y = cursor_y - CURSOR_GAP - height
    if x + width > right:
        x = cursor_x - CURSOR_GAP - width
    if y < top:
        y = cursor_y + CURSOR_GAP
    return (
        max(left, min(x, right - width)),
        max(top, min(y, bottom - height)),
    )


@dataclass
class _Command:
    action: str


class _PixelMagnifier:
    def __init__(self):
        self._commands: queue.Queue[_Command] = queue.Queue()
        self._thread = None
        self._started = threading.Event()
        self._ready_ok = False

    def start(self):
        if not IS_WINDOWS:
            return False
        self.stop()
        if self._thread and self._thread.is_alive():
            return False
        self._commands = queue.Queue()
        self._ready_ok = False
        self._started.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="calibration-pixel-magnifier",
            daemon=True,
        )
        self._thread.start()
        return self._started.wait(timeout=1.5) and self._ready_ok

    def stop(self):
        thread = self._thread
        if thread and thread.is_alive():
            self._commands.put(_Command("stop"))
            thread.join(timeout=1.5)
        if not thread or not thread.is_alive():
            self._thread = None

    def _run(self):
        try:
            import ctypes
            from ctypes import wintypes

            from . import win_input, win_pixel

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            LRESULT = ctypes.c_ssize_t
            WNDPROC = ctypes.WINFUNCTYPE(
                LRESULT,
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            )

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            class PAINTSTRUCT(ctypes.Structure):
                _fields_ = [
                    ("hdc", wintypes.HDC),
                    ("fErase", wintypes.BOOL),
                    ("rcPaint", RECT),
                    ("fRestore", wintypes.BOOL),
                    ("fIncUpdate", wintypes.BOOL),
                    ("rgbReserved", wintypes.BYTE * 32),
                ]

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", wintypes.UINT),
                    ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE),
                    ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR),
                    ("lpszClassName", wintypes.LPCWSTR),
                ]

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            class BITMAPINFO(ctypes.Structure):
                _fields_ = [
                    ("bmiHeader", BITMAPINFOHEADER),
                    ("bmiColors", wintypes.DWORD * 3),
                ]

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            class MSG(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("message", wintypes.UINT),
                    ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM),
                    ("time", wintypes.DWORD),
                    ("pt", POINT),
                ]

            user32.DefWindowProcW.argtypes = (
                wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            )
            user32.DefWindowProcW.restype = LRESULT
            user32.BeginPaint.argtypes = (wintypes.HWND, ctypes.POINTER(PAINTSTRUCT))
            user32.BeginPaint.restype = wintypes.HDC
            user32.EndPaint.argtypes = (wintypes.HWND, ctypes.POINTER(PAINTSTRUCT))
            user32.MonitorFromPoint.argtypes = (POINT, wintypes.DWORD)
            user32.MonitorFromPoint.restype = wintypes.HANDLE
            user32.GetMonitorInfoW.argtypes = (
                wintypes.HANDLE, ctypes.POINTER(MONITORINFO),
            )
            user32.RegisterClassW.argtypes = (ctypes.POINTER(WNDCLASSW),)
            user32.RegisterClassW.restype = wintypes.ATOM
            user32.CreateWindowExW.argtypes = (
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p,
            )
            user32.CreateWindowExW.restype = wintypes.HWND
            user32.SetWindowRgn.argtypes = (
                wintypes.HWND, wintypes.HANDLE, wintypes.BOOL,
            )
            user32.SetWindowPos.argtypes = (
                wintypes.HWND, wintypes.HWND,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.UINT,
            )
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.PeekMessageW.argtypes = (
                ctypes.POINTER(MSG), wintypes.HWND,
                wintypes.UINT, wintypes.UINT, wintypes.UINT,
            )
            user32.DispatchMessageW.restype = LRESULT
            user32.InvalidateRect.argtypes = (
                wintypes.HWND, ctypes.POINTER(RECT), wintypes.BOOL,
            )
            user32.UpdateWindow.argtypes = (wintypes.HWND,)
            user32.UpdateWindow.restype = wintypes.BOOL
            user32.IsWindow.argtypes = (wintypes.HWND,)
            user32.DestroyWindow.argtypes = (wintypes.HWND,)
            user32.UnregisterClassW.argtypes = (wintypes.LPCWSTR, wintypes.HINSTANCE)
            gdi32.CreateSolidBrush.restype = wintypes.HBRUSH
            gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
            gdi32.SelectObject.restype = wintypes.HGDIOBJ
            gdi32.GetStockObject.argtypes = (ctypes.c_int,)
            gdi32.GetStockObject.restype = wintypes.HGDIOBJ
            gdi32.Ellipse.argtypes = (
                wintypes.HDC,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            )
            gdi32.Ellipse.restype = wintypes.BOOL
            gdi32.SetStretchBltMode.argtypes = (wintypes.HDC, ctypes.c_int)
            gdi32.SetStretchBltMode.restype = ctypes.c_int
            gdi32.CreateEllipticRgn.argtypes = (
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            )
            gdi32.CreateEllipticRgn.restype = wintypes.HANDLE
            gdi32.StretchDIBits.argtypes = (
                wintypes.HDC,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.POINTER(BITMAPINFO),
                wintypes.UINT, wintypes.DWORD,
            )
            gdi32.DeleteObject.argtypes = (wintypes.HANDLE,)
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            black_brush = gdi32.CreateSolidBrush(0)
            marker_outer_brush = gdi32.CreateSolidBrush(0x00120F0D)
            marker_inner_brush = gdi32.CreateSolidBrush(0x00FF8972)
            frame = {"pixels": bytes(SAMPLE_SIZE * SAMPLE_SIZE * 4)}
            bitmap_info = BITMAPINFO()
            bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bitmap_info.bmiHeader.biWidth = SAMPLE_SIZE
            bitmap_info.bmiHeader.biHeight = -SAMPLE_SIZE
            bitmap_info.bmiHeader.biPlanes = 1
            bitmap_info.bmiHeader.biBitCount = 32
            bitmap_info.bmiHeader.biCompression = 0

            @WNDPROC
            def wndproc(hwnd, message, wparam, lparam):
                if message == 0x0014:
                    return 1
                if message == 0x000F:
                    paint = PAINTSTRUCT()
                    hdc = user32.BeginPaint(hwnd, ctypes.byref(paint))
                    try:
                        buffer = ctypes.create_string_buffer(frame["pixels"])
                        gdi32.SetStretchBltMode(hdc, 3)
                        gdi32.StretchDIBits(
                            hdc,
                            0,
                            0,
                            WINDOW_WIDTH,
                            WINDOW_HEIGHT,
                            0,
                            0,
                            SAMPLE_SIZE,
                            SAMPLE_SIZE,
                            buffer,
                            ctypes.byref(bitmap_info),
                            0,
                            0x00CC0020,
                        )



                        centre_x = WINDOW_WIDTH // 2
                        centre_y = WINDOW_HEIGHT // 2
                        previous_pen = gdi32.SelectObject(
                            hdc,
                            gdi32.GetStockObject(8),
                        )
                        previous_brush = gdi32.SelectObject(hdc, marker_outer_brush)
                        radius = CENTER_DOT_OUTER_RADIUS
                        gdi32.Ellipse(
                            hdc,
                            centre_x - radius,
                            centre_y - radius,
                            centre_x + radius + 1,
                            centre_y + radius + 1,
                        )
                        gdi32.SelectObject(hdc, marker_inner_brush)
                        radius = CENTER_DOT_INNER_RADIUS
                        gdi32.Ellipse(
                            hdc,
                            centre_x - radius,
                            centre_y - radius,
                            centre_x + radius + 1,
                            centre_y + radius + 1,
                        )
                        gdi32.SelectObject(hdc, previous_brush)
                        gdi32.SelectObject(hdc, previous_pen)
                    finally:
                        user32.EndPaint(hwnd, ctypes.byref(paint))
                    return 0
                if message == 0x0002:
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(hwnd, message, wparam, lparam)

            class_name = "SolRichCalibrationPixelMagnifier"
            instance = kernel32.GetModuleHandleW(None)
            window_class = WNDCLASSW()
            window_class.lpfnWndProc = wndproc
            window_class.hInstance = instance
            window_class.hbrBackground = black_brush
            window_class.lpszClassName = class_name
            atom = user32.RegisterClassW(ctypes.byref(window_class))
            if not atom and ctypes.get_last_error() != 1410:
                raise ctypes.WinError(ctypes.get_last_error())

            extended_style = (
                0x00000008
                | 0x00000020
                | 0x00000080
                | 0x08000000
            )
            hwnd = user32.CreateWindowExW(
                extended_style,
                class_name,
                "",
                0x80000000,
                0,
                0,
                WINDOW_WIDTH,
                WINDOW_HEIGHT,
                None,
                None,
                instance,
                None,
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())

            circle = gdi32.CreateEllipticRgn(0, 0, WINDOW_WIDTH + 1, WINDOW_HEIGHT + 1)
            if circle and not user32.SetWindowRgn(hwnd, circle, True):
                gdi32.DeleteObject(circle)

            def monitor_rect(x, y):
                handle = user32.MonitorFromPoint(POINT(int(x), int(y)), 2)
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if handle and user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                    rect = info.rcWork
                    return rect.left, rect.top, rect.right, rect.bottom
                left = user32.GetSystemMetrics(76)
                top = user32.GetSystemMetrics(77)
                return (
                    left,
                    top,
                    left + user32.GetSystemMetrics(78),
                    top + user32.GetSystemMetrics(79),
                )

            user32.ShowWindow(hwnd, 4)
            self._ready_ok = True
            self._started.set()
            message = MSG()
            next_frame = 0.0
            running = True
            while running:
                while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                    if message.message == 0x0012:
                        running = False
                        break
                    user32.TranslateMessage(ctypes.byref(message))
                    user32.DispatchMessageW(ctypes.byref(message))
                try:
                    while True:
                        if self._commands.get_nowait().action == "stop":
                            running = False
                except queue.Empty:
                    pass
                if not running:
                    break

                now = time.monotonic()
                if now >= next_frame:
                    next_frame = now + (1 / 60)
                    cursor_x, cursor_y = win_input.get_cursor_pos()
                    x, y = place_near_cursor(
                        (cursor_x, cursor_y),
                        monitor_rect(cursor_x, cursor_y),
                    )




                    user32.SetWindowPos(
                        hwnd,
                        wintypes.HWND(-1),
                        x,
                        y,
                        WINDOW_WIDTH,
                        WINDOW_HEIGHT,
                        0x0010 | 0x0040,
                    )
                    try:
                        radius = SAMPLE_SIZE // 2
                        _, _, frame["pixels"] = win_pixel.grab_region(
                            cursor_x - radius,
                            cursor_y - radius,
                            SAMPLE_SIZE,
                            SAMPLE_SIZE,
                        )
                    except Exception:
                        pass
                    user32.InvalidateRect(hwnd, None, False)


                    user32.UpdateWindow(hwnd)
                time.sleep(0.008)

            if user32.IsWindow(hwnd):
                user32.DestroyWindow(hwnd)
            if black_brush:
                gdi32.DeleteObject(black_brush)
            if marker_outer_brush:
                gdi32.DeleteObject(marker_outer_brush)
            if marker_inner_brush:
                gdi32.DeleteObject(marker_inner_brush)
            user32.UnregisterClassW(class_name, instance)
        except Exception as error:
            print(f"[CalibrationMagnifier] Could not start: {error}")
            self._ready_ok = False
            self._started.set()


_MAGNIFIER = _PixelMagnifier()


def show():
    return _MAGNIFIER.start()


def hide():
    _MAGNIFIER.stop()
