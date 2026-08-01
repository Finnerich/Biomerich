import sys
import time

IS_WINDOWS = sys.platform == "win32"

_IS_WINDOWS = IS_WINDOWS

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1

    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_SCANCODE = 0x0008

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_VIRTUALDESK = 0x4000

    WHEEL_DELTA = 120

    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79

    MAPVK_VK_TO_VSC = 0

    VK_LBUTTON = 0x01
    VK_BACK = 0x08
    VK_CONTROL = 0x11
    VK_A = 0x41

    _VK_NAMES = {
        "space": 0x20,
        "enter": 0x0D,
        "return": 0x0D,
        "esc": 0x1B,
        "escape": 0x1B,
        "tab": 0x09,
        "shift": 0x10,
        "ctrl": 0x11,
        "alt": 0x12,
        "backspace": 0x08,
        "up": 0x26,
        "down": 0x28,
        "left": 0x25,
        "right": 0x27,
    }

    def _vk_for(name):
        key = str(name).lower().strip()
        if key in _VK_NAMES:
            return _VK_NAMES[key]
        if len(key) == 1:
            ch = key.upper()
            if "A" <= ch <= "Z" or "0" <= ch <= "9":
                return ord(ch)
        return None

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

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = wintypes.SHORT
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    user32.GetSystemMetrics.restype = ctypes.c_int

    def _make_dpi_aware():
        try:

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    _make_dpi_aware()

    def get_cursor_pos():
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return (int(pt.x), int(pt.y))

    def _send_mouse(flags, dx=0, dy=0):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi = MOUSEINPUT(dx, dy, 0, flags, 0, 0)
        return int(user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)))

    def _send_left_click_atomic():
        
        inputs = (INPUT * 2)()
        inputs[0].type = INPUT_MOUSE
        inputs[0].u.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, 0)
        inputs[1].type = INPUT_MOUSE
        inputs[1].u.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, 0)
        sent = int(user32.SendInput(2, inputs, ctypes.sizeof(INPUT)))
        if sent != 2:


            _send_mouse(MOUSEEVENTF_LEFTUP)
        return sent == 2

    def release_mouse_buttons(settle=0.03):
        
        released = _send_mouse(MOUSEEVENTF_LEFTUP) == 1
        if settle > 0:
            time.sleep(settle)
        return released

    def _abs_norm(x, y):
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        nx = int(round((x - vx) * 65535.0 / max(1, vw - 1)))
        ny = int(round((y - vy) * 65535.0 / max(1, vh - 1)))
        return max(0, min(65535, nx)), max(0, min(65535, ny))

    def _move_event(x, y):
        nx, ny = _abs_norm(x, y)
        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        _send_mouse(flags, nx, ny)

    def move_to(x, y, duration=0.22, steps=None):
        x, y = int(x), int(y)
        sx, sy = get_cursor_pos()
        dist = max(abs(x - sx), abs(y - sy))
        if steps is None:
            steps = max(10, min(70, dist // 10))
        steps = max(1, steps)
        for i in range(1, steps + 1):
            t = i / steps
            te = t * t * (3 - 2 * t)
            nx = int(round(sx + (x - sx) * te))
            ny = int(round(sy + (y - sy) * te))
            _move_event(nx, ny)
            user32.SetCursorPos(nx, ny)
            time.sleep(duration / steps)
        _move_event(x, y)
        user32.SetCursorPos(x, y)

    def click_at(x, y, settle=0.12):
        x, y = int(x), int(y)
        move_to(x, y)
        time.sleep(settle)
        _move_event(x, y)
        user32.SetCursorPos(x, y)
        time.sleep(0.05)
        clicked = _send_left_click_atomic()
        time.sleep(0.06)
        return clicked

    def click_here(settle=0.02):
        clicked = _send_left_click_atomic()
        if settle > 0:
            time.sleep(settle)
        return clicked

    def look(dx, dy, steps=20, step_delay=0.008):
        
        dx, dy = int(dx), int(dy)
        steps = max(1, int(steps))
        accx = accy = 0.0
        sx, sy = dx / steps, dy / steps
        for _ in range(steps):
            accx += sx
            accy += sy
            ix, iy = int(round(accx)), int(round(accy))
            accx -= ix
            accy -= iy
            if ix or iy:
                _send_mouse(MOUSEEVENTF_MOVE, ix, iy)
            time.sleep(step_delay)

    def _send_wheel(amount):
        inp = INPUT()
        inp.type = INPUT_MOUSE
        inp.u.mi = MOUSEINPUT(0, 0, amount & 0xFFFFFFFF, MOUSEEVENTF_WHEEL, 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def scroll(notches, step_delay=0.02):
        notches = int(notches)
        direction = 1 if notches >= 0 else -1
        for _ in range(abs(notches)):
            _send_wheel(direction * WHEEL_DELTA)
            time.sleep(step_delay)

    def _send_key_vk(vk, key_up):
        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.u.ki = KEYBDINPUT(0, scan, flags, 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _tap_vk(vk):
        _send_key_vk(vk, False)
        time.sleep(0.02)
        _send_key_vk(vk, True)

    def key_down(name):
        vk = _vk_for(name)
        if vk is not None:
            _send_key_vk(vk, False)

    def key_up(name):
        vk = _vk_for(name)
        if vk is not None:
            _send_key_vk(vk, True)

    def press_key(name, settle=0.0):
        vk = _vk_for(name)
        if vk is None:
            return
        _send_key_vk(vk, False)
        time.sleep(0.04)
        _send_key_vk(vk, True)
        if settle > 0:
            time.sleep(settle)

    def hold_key(name, duration):
        vk = _vk_for(name)
        if vk is None:
            return
        _send_key_vk(vk, False)
        time.sleep(max(0.0, float(duration)))
        _send_key_vk(vk, True)

    def _send_unicode_char(ch):
        code = ord(ch)
        for key_up in (False, True):
            flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if key_up else 0)
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.u.ki = KEYBDINPUT(0, code, flags, 0, 0)
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def type_text(text, per_char=0.022):
        for ch in str(text):
            _send_unicode_char(ch)
            time.sleep(per_char)

    def select_all_and_clear():
        _send_key_vk(VK_CONTROL, False)
        time.sleep(0.01)
        _tap_vk(VK_A)
        _send_key_vk(VK_CONTROL, True)
        time.sleep(0.04)
        _tap_vk(VK_BACK)

    def _lmb_down():
        return bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)

    def capture_next_click(timeout=30.0, should_cancel=None, poll=0.01):
        deadline = time.time() + max(1.0, timeout)

        while _lmb_down():
            if time.time() > deadline:
                return None
            if should_cancel and should_cancel():
                return None
            time.sleep(poll)

        while True:
            if time.time() > deadline:
                return None
            if should_cancel and should_cancel():
                return None
            if _lmb_down():
                pos = get_cursor_pos()

                while _lmb_down():
                    time.sleep(0.005)
                return pos
            time.sleep(poll)

else:
    def get_cursor_pos():
        return (0, 0)

    def move_to(x, y, duration=0.22, steps=None):
        return

    def click_at(x, y, settle=0.12):
        return True

    def click_here(settle=0.02):
        return True

    def release_mouse_buttons(settle=0.03):
        return True

    def scroll(notches, step_delay=0.02):
        return

    def look(dx, dy, steps=20, step_delay=0.008):
        return

    def key_down(name):
        return

    def key_up(name):
        return

    def press_key(name, settle=0.0):
        return

    def hold_key(name, duration):
        return

    def type_text(text, per_char=0.012):
        return

    def select_all_and_clear():
        return

    def capture_next_click(timeout=30.0, should_cancel=None, poll=0.01):
        return None
