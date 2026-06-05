import sys
import time
import threading

_IS_WINDOWS = sys.platform == "win32"

VK_SPACE = 0x20
VK_I = 0x49
VK_O = 0x4F

ROBLOX_EXE = "robloxplayerbeta.exe"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    SW_RESTORE = 9
    INPUT_KEYBOARD = 1
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    ASFW_ANY = 0xFFFFFFFF

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ULONG_PTR),
        ]

    class _INPUTunion(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT

    def _process_name(hwnd):
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
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

    def _roblox_windows():
        result = []

        def _cb(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if _process_name(hwnd) == ROBLOX_EXE:
                result.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(_cb), 0)
        return result

    def _foreground_window():
        return user32.GetForegroundWindow()

    def _force_foreground(hwnd):
        if not hwnd:
            return False
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        if user32.GetForegroundWindow() == hwnd:
            return True
        try:
            user32.AllowSetForegroundWindow(ASFW_ANY)
        except Exception:
            pass
        fg_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
        this_thread = kernel32.GetCurrentThreadId()
        attached = False
        if fg_thread and fg_thread != this_thread:
            attached = bool(user32.AttachThreadInput(fg_thread, this_thread, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(fg_thread, this_thread, False)
        return user32.GetForegroundWindow() == hwnd

    def _send_scan(scan, key_up):
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki = KEYBDINPUT(0, scan, flags, 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _tap_key(vk):
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        _send_scan(scan, False)
        time.sleep(0.04)
        _send_scan(scan, True)

    def _run_cycle(action):
        previous = _foreground_window()
        targets = _roblox_windows()
        if not targets:
            return
        for hwnd in targets:
            if not _force_foreground(hwnd):
                continue
            time.sleep(0.18)
            if action == "zoom":
                _tap_key(VK_I)
                time.sleep(0.05)
                _tap_key(VK_O)
            else:
                _tap_key(VK_SPACE)
            time.sleep(0.08)
        if previous:
            _force_foreground(previous)

else:
    def _run_cycle(action):
        return


class AntiAfk:
    def __init__(self, config, is_running):
        self.config = config
        self._is_running = is_running
        self._stop = threading.Event()
        self._thread = None

    def enabled(self):
        return bool(self.config.settings.get("antiAfkEnabled", False))

    def _action(self):
        value = self.config.settings.get("antiAfkAction", "space")
        return "zoom" if value == "zoom" else "space"

    def _interval(self):
        try:
            value = int(self.config.settings.get("antiAfkInterval", 300))
        except (TypeError, ValueError):
            value = 300
        return max(30, min(900, value))

    def start(self):
        if not _IS_WINDOWS:
            return
        if not self.enabled():
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[AntiAfk] Started.")

    def stop(self):
        if self._thread:
            print("[AntiAfk] Stopped.")
        self._stop.set()
        self._thread = None

    def _loop(self):
        self._fire()
        while not self._stop.wait(self._interval()):
            if self._stop.is_set():
                break
            self._fire()

    def _fire(self):
        if self._stop.is_set() or not self._is_running() or not self.enabled():
            return
        try:
            _run_cycle(self._action())
        except Exception as e:
            print(f"[AntiAfk] Cycle failed: {e}")
