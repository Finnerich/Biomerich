import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0
    BI_RGB = 0

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
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.BitBlt.argtypes = (
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    )
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = (
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    )
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.GetPixel.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi32.GetPixel.restype = wintypes.DWORD
    gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
    gdi32.DeleteDC.argtypes = (wintypes.HDC,)
    user32.GetDC.argtypes = (wintypes.HWND,)
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)

    def get_pixel(x, y):
        hdc = user32.GetDC(0)
        try:
            ref = gdi32.GetPixel(hdc, int(x), int(y))
            if ref == 0xFFFFFFFF:
                return None
            r = ref & 0xFF
            g = (ref >> 8) & 0xFF
            b = (ref >> 16) & 0xFF
            return (r, g, b)
        finally:
            user32.ReleaseDC(0, hdc)

    def grab_region(x, y, w, h):
        w = max(1, int(w))
        h = max(1, int(h))
        screen = user32.GetDC(0)
        mem_dc = gdi32.CreateCompatibleDC(screen)
        bmp = gdi32.CreateCompatibleBitmap(screen, w, h)
        old = gdi32.SelectObject(mem_dc, bmp)
        try:
            gdi32.BitBlt(mem_dc, 0, 0, w, h, screen, int(x), int(y), SRCCOPY)
            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = w
            info.bmiHeader.biHeight = -h
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = BI_RGB
            buf = (ctypes.c_char * (w * h * 4))()
            gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(info), DIB_RGB_COLORS)
            return (w, h, bytes(buf))
        finally:
            gdi32.SelectObject(mem_dc, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem_dc)
            user32.ReleaseDC(0, screen)

    def _tol_table(center, tol):
        
        lo = max(0, int(center) - tol)
        hi = min(255, int(center) + tol)
        tbl = bytearray(256)
        for i in range(lo, hi + 1):
            tbl[i] = 1
        return bytes(tbl)

    def color_in_region(x, y, w, h, target_rgb, tol):
        gw, gh, data = grab_region(x, y, w, h)
        if not data:
            return False
        tr, tg, tb = target_rgb
        t = int(tol)
        r_mask = data[2::4].translate(_tol_table(tr, t))
        g_mask = data[1::4].translate(_tol_table(tg, t))
        b_mask = data[0::4].translate(_tol_table(tb, t))
        combined = (int.from_bytes(r_mask, "big")
                    & int.from_bytes(g_mask, "big")
                    & int.from_bytes(b_mask, "big"))
        return combined != 0

    def color_in_region_pc(x, y, w, h, target_rgb, tol_rgb):
        
        gw, gh, data = grab_region(x, y, w, h)
        if not data:
            return False
        tr, tg, tb = target_rgb
        ttr, ttg, ttb = (int(v) for v in tol_rgb)
        r_mask = data[2::4].translate(_tol_table(tr, ttr))
        g_mask = data[1::4].translate(_tol_table(tg, ttg))
        b_mask = data[0::4].translate(_tol_table(tb, ttb))
        combined = (int.from_bytes(r_mask, "big")
                    & int.from_bytes(g_mask, "big")
                    & int.from_bytes(b_mask, "big"))
        return combined != 0

    def color_block_in_region_pc(x, y, w, h, target_rgb, tol_rgb,
                                 min_columns=2, min_rows=3):
        
        gw, gh, data = grab_region(x, y, w, h)
        if not data:
            return False
        tr, tg, tb = target_rgb
        ttr, ttg, ttb = (int(v) for v in tol_rgb)
        r_mask = data[2::4].translate(_tol_table(tr, ttr))
        g_mask = data[1::4].translate(_tol_table(tg, ttg))
        b_mask = data[0::4].translate(_tol_table(tb, ttb))
        combined_int = (int.from_bytes(r_mask, "big")
                        & int.from_bytes(g_mask, "big")
                        & int.from_bytes(b_mask, "big"))
        if not combined_int:
            return False
        combined = combined_int.to_bytes(len(r_mask), "big")

        needed_columns = max(1, int(min_columns))
        needed_rows = max(1, int(min_rows))
        run = 0
        for column in range(gw):
            if sum(combined[column::gw]) >= needed_rows:
                run += 1
                if run >= needed_columns:
                    return True
            else:
                run = 0
        return False

    def color_match(rgb, target_rgb, tol):
        if rgb is None:
            return False
        t = int(tol)
        return (
            abs(rgb[0] - target_rgb[0]) <= t
            and abs(rgb[1] - target_rgb[1]) <= t
            and abs(rgb[2] - target_rgb[2]) <= t
        )

    def rightmost_match(x, y, w, h, target_rgb, tol):
        gw, gh, data = grab_region(x, y, w, h)
        tr, tg, tb = target_rgb
        t = int(tol)
        for col in range(gw - 1, -1, -1):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]
                g = data[o + 1]
                r = data[o + 2]
                if abs(r - tr) <= t and abs(g - tg) <= t and abs(b - tb) <= t:
                    return col
        return -1

    def match_columns(x, y, w, h, target_rgb, tol):
        gw, gh, data = grab_region(x, y, w, h)
        tr, tg, tb = target_rgb
        t = int(tol)
        count = 0
        for col in range(gw):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]
                g = data[o + 1]
                r = data[o + 2]
                if abs(r - tr) <= t and abs(g - tg) <= t and abs(b - tb) <= t:
                    count += 1
                    break
        return count

    def match_extent(x, y, w, h, target_rgb, tol):
        gw, gh, data = grab_region(x, y, w, h)
        tr, tg, tb = target_rgb
        t = int(tol)
        lo = -1
        hi = -1
        for col in range(gw):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]
                g = data[o + 1]
                r = data[o + 2]
                if abs(r - tr) <= t and abs(g - tg) <= t and abs(b - tb) <= t:
                    if lo < 0:
                        lo = col
                    hi = col
                    break
        return (lo, hi)

    def bar_extent_from_right(x, y, w, h, target_rgb, tol):

        gw, gh, data = grab_region(x, y, w, h)
        tr, tg, tb = target_rgb
        t = int(tol)

        hi = -1
        for col in range(gw - 1, -1, -1):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]; g = data[o + 1]; r = data[o + 2]
                if abs(r - tr) <= t and abs(g - tg) <= t and abs(b - tb) <= t:
                    hi = col
                    break
            if hi >= 0:
                break

        if hi < 0:
            return (-1, -1)

        lo = -1
        for col in range(gw):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]; g = data[o + 1]; r = data[o + 2]
                if abs(r - tr) <= t and abs(g - tg) <= t and abs(b - tb) <= t:
                    lo = col
                    break
            if lo >= 0:
                break

        return (lo, hi)

    def find_overlay_edge(x, y, w, h, overlay_max_r, overlay_min_b):

        gw, gh, data = grab_region(x, y, w, h)
        omr = int(overlay_max_r)
        omb = int(overlay_min_b)
        in_overlay = False
        for col in range(gw):
            col_has_overlay = False
            for row in range(gh):
                o = (row * gw + col) * 4
                b_val = data[o]
                g_val = data[o + 1]
                r_val = data[o + 2]
                if r_val < 25 and g_val < 50 and b_val < 50:
                    continue
                if r_val < omr and b_val > omb:
                    col_has_overlay = True
                    break
            if col_has_overlay:
                in_overlay = True
            elif in_overlay:
                return col
        return -1

    def find_arrow_x(x, y, w, h, bar_color, bar_tol, arrow_tol=55):

        gw, gh, data = grab_region(x, y, w, h)
        br, bg, bb = bar_color
        bt = int(bar_tol)
        for col in range(gw):
            for row in range(gh):
                o = (row * gw + col) * 4
                b = data[o]
                g = data[o + 1]
                r = data[o + 2]
                if r < 30 and g < 60 and b < 60:
                    continue
                if abs(r - br) <= bt and abs(g - bg) <= bt and abs(b - bb) <= bt:
                    continue
                return col
        return -1

else:
    def get_pixel(x, y):
        return None

    def grab_region(x, y, w, h):
        return (0, 0, b"")

    def color_in_region(x, y, w, h, target_rgb, tol):
        return False

    def color_in_region_pc(x, y, w, h, target_rgb, tol_rgb):
        return False

    def color_block_in_region_pc(x, y, w, h, target_rgb, tol_rgb,
                                 min_columns=2, min_rows=3):
        return False

    def color_match(rgb, target_rgb, tol):
        return False

    def rightmost_match(x, y, w, h, target_rgb, tol):
        return -1

    def match_columns(x, y, w, h, target_rgb, tol):
        return 0

    def find_arrow_x(x, y, w, h, bar_color, bar_tol, arrow_tol=55):
        return -1

    def bar_extent_from_right(x, y, w, h, target_rgb, tol):
        return (-1, -1)

    def find_overlay_edge(x, y, w, h, overlay_max_r, overlay_min_b):
        return -1

    def match_extent(x, y, w, h, target_rgb, tol):
        return (-1, -1)
