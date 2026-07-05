import sys
import queue
import traceback

IS_WINDOWS = sys.platform == "win32"

_TRANSPARENT_KEY = "#010203"

def _real_thread():

    try:
        from gevent import monkey
        if monkey.is_module_patched("threading"):
            return monkey.get_original("threading", "Thread")
    except Exception:
        pass
    from threading import Thread
    return Thread

def _virtual_screen():
    if not IS_WINDOWS:
        return (0, 0, 1920, 1080)
    import ctypes
    user32 = ctypes.windll.user32
    x = user32.GetSystemMetrics(76)
    y = user32.GetSystemMetrics(77)
    w = user32.GetSystemMetrics(78)
    h = user32.GetSystemMetrics(79)
    if w <= 0 or h <= 0:
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        x, y = 0, 0
    return (x, y, w, h)

def _make_click_through(root):
    if not IS_WINDOWS:
        return
    try:
        import ctypes
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        user32 = ctypes.windll.user32
        hwnd = root.winfo_id()
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = parent
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass

class _Overlay:
    def __init__(self):
        self._q = queue.Queue()
        self._thread = None
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        Thread = _real_thread()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def show(self, payload, duration):
        self.start()
        self._q.put((payload, duration))

    def _run(self):
        try:
            import tkinter as tk
        except Exception as e:
            print(f"[Overlay] tkinter unavailable: {e}")
            self._started = False
            return

        try:
            vx, vy, vw, vh = _virtual_screen()
            root = tk.Tk()
            root.withdraw()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            try:
                root.attributes("-transparentcolor", _TRANSPARENT_KEY)
            except tk.TclError:
                pass
            root.configure(bg=_TRANSPARENT_KEY)
            root.geometry(f"{vw}x{vh}+{vx}+{vy}")

            canvas = tk.Canvas(root, width=vw, height=vh, bg=_TRANSPARENT_KEY,
                               highlightthickness=0, bd=0)
            canvas.pack(fill="both", expand=True)

            state = {"hide_after": None}

            def draw(payload):
                canvas.delete("all")
                if isinstance(payload, dict):
                    points = payload.get("points", []) or []
                    regions = payload.get("regions", []) or []
                else:
                    points = payload or []
                    regions = []
                ox, oy = _virtual_screen()[0], _virtual_screen()[1]
                for rgn in regions:
                    try:
                        rx = int(rgn["x"]) - ox
                        ry = int(rgn["y"]) - oy
                        rw = int(rgn["w"])
                        rh = int(rgn["h"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if rw <= 0 or rh <= 0:
                        continue
                    color = rgn.get("color", "#22d3ee")
                    label = str(rgn.get("label", ""))

                    canvas.create_rectangle(rx, ry, rx + rw, ry + rh,
                                            fill=color, outline="", stipple="gray25")
                    canvas.create_rectangle(rx, ry, rx + rw, ry + rh,
                                            fill="", outline=color, width=2)
                    canvas.create_rectangle(rx + 1, ry + 1, rx + rw - 1, ry + rh - 1,
                                            fill="", outline="#ffffff", width=1)
                    if label:
                        ly = ry - 9 if ry - 18 > oy else ry + rh + 11
                        tid = canvas.create_text(rx + 2, ly, text=label, anchor="w",
                                                 fill="#ffffff",
                                                 font=("Segoe UI", 10, "bold"))
                        bb = canvas.bbox(tid)
                        if bb:
                            pad = 5
                            rect = canvas.create_rectangle(bb[0] - pad, bb[1] - pad,
                                                           bb[2] + pad, bb[3] + pad,
                                                           fill="#11121e", outline=color,
                                                           width=1)
                            canvas.tag_lower(rect, tid)
                for p in points:
                    try:
                        x = int(p["x"]) - ox
                        y = int(p["y"]) - oy
                    except (KeyError, TypeError, ValueError):
                        continue
                    label = str(p.get("label", ""))
                    color = p.get("color", "#ff3b3b")
                    r = 8
                    canvas.create_oval(x - r - 5, y - r - 5, x + r + 5, y + r + 5,
                                       outline=color, width=2)
                    canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
                    canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#ffffff", outline="")
                    if label:
                        tx, ty = x + 17, y - 9
                        tid = canvas.create_text(tx, ty, text=label, anchor="w",
                                                 fill="#ffffff", font=("Segoe UI", 10, "bold"))
                        bb = canvas.bbox(tid)
                        if bb:
                            pad = 5
                            rect = canvas.create_rectangle(bb[0] - pad, bb[1] - pad,
                                                           bb[2] + pad, bb[3] + pad,
                                                           fill="#11121e", outline=color, width=1)
                            canvas.tag_lower(rect, tid)

            def hide():
                state["hide_after"] = None
                try:
                    root.withdraw()
                except Exception:
                    pass

            def poll():
                try:
                    while True:
                        payload, duration = self._q.get_nowait()
                        draw(payload)
                        root.deiconify()
                        root.lift()
                        root.attributes("-topmost", True)
                        _make_click_through(root)
                        if state["hide_after"] is not None:
                            try:
                                root.after_cancel(state["hide_after"])
                            except Exception:
                                pass
                        state["hide_after"] = root.after(
                            int(max(0.5, duration) * 1000), hide)
                except queue.Empty:
                    pass
                root.after(60, poll)

            root.after(60, poll)
            root.mainloop()
        except Exception:
            print("[Overlay] crashed:")
            traceback.print_exc()
            self._started = False

_OVERLAY = _Overlay()

def show_points(points, duration=4.0, regions=None):
    if not IS_WINDOWS:
        return {"ok": False, "error": "not_windows"}
    pts = [p for p in (points or []) if isinstance(p, dict) and "x" in p and "y" in p]
    rgns = [r for r in (regions or [])
            if isinstance(r, dict) and all(k in r for k in ("x", "y", "w", "h"))]
    if not pts and not rgns:
        return {"ok": False, "error": "no_points"}
    try:
        _OVERLAY.show({"points": pts, "regions": rgns}, float(duration))
        return {"ok": True, "count": len(pts) + len(rgns)}
    except Exception as e:
        print(f"[Overlay] show failed: {e}")
        return {"ok": False, "error": "show_failed"}
