

import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    def _virtual_screen():

        x = _user32.GetSystemMetrics(76)
        y = _user32.GetSystemMetrics(77)
        w = _user32.GetSystemMetrics(78)
        h = _user32.GetSystemMetrics(79)
        if not w or not h:
            w = _user32.GetSystemMetrics(0)
            h = _user32.GetSystemMetrics(1)
            x, y = 0, 0
        return int(x), int(y), int(w), int(h)

    def _primary_screen():

        w = _user32.GetSystemMetrics(0)
        h = _user32.GetSystemMetrics(1)
        return 0, 0, int(w), int(h)
else:
    def _virtual_screen():
        return (0, 0, 0, 0)

    def _primary_screen():
        return (0, 0, 0, 0)

def _clamp_to_primary(x, y, w, h):
    
    px, py, pw, ph = _primary_screen()
    if pw <= 0 or ph <= 0:
        return None
    x0 = max(x, px)
    y0 = max(y, py)
    x1 = min(x + w, px + pw)
    y1 = min(y + h, py + ph)
    if x1 <= x0 or y1 <= y0:
        return None
    return int(x0), int(y0), int(x1 - x0), int(y1 - y0)

def _encode_png(w, h, bgra):
    
    try:
        from PIL import Image
        import io
    except Exception as e:
        print(f"[Screenshot] PIL not available: {e}")
        return None
    try:
        img = Image.frombuffer("RGBA", (w, h), bgra, "raw", "BGRA", 0, 1)
        img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception as e:
        print(f"[Screenshot] PNG encode failed: {e}")
        return None

def grab_region_png(x, y, w, h):
    
    if not IS_WINDOWS:
        return None
    try:
        from . import win_pixel
        gw, gh, data = win_pixel.grab_region(int(x), int(y), int(w), int(h))
        return _encode_png(gw, gh, data)
    except Exception as e:
        print(f"[Screenshot] region grab failed: {e}")
        return None

def grab_window_png(rect):
    
    if not IS_WINDOWS or not rect:
        return None
    try:
        x, y, w, h = rect
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    clamped = _clamp_to_primary(x, y, w, h)
    if clamped is None:
        print("[Screenshot] Roblox window is not on the primary monitor — skipping screenshot.")
        return None
    return grab_region_png(*clamped)

def grab_fullscreen_png():
    
    if not IS_WINDOWS:
        return None
    x, y, w, h = _primary_screen()
    if w <= 0 or h <= 0:
        return None
    return grab_region_png(x, y, w, h)
