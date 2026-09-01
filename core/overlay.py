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
        WS_EX_NOACTIVATE = 0x08000000
        user32 = ctypes.windll.user32
        hwnd = root.winfo_id()
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = parent
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
        )
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        pass

class _Overlay:
    def __init__(self):
        self._q = queue.Queue()
        self._thread = None
        self._started = False
        self._guide_generation = 0
        self._guide_image_cache = {}

    def start(self):
        if self._started:
            return
        self._started = True
        Thread = _real_thread()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def show(self, payload, duration):
        self.start()
        self._q.put(("show", payload, duration))

    def show_guide(self, guide, duration):
        
        self._guide_generation += 1
        generation = self._guide_generation
        payload = {"guide": dict(guide)}
        self.show(payload, duration)

        image_urls = list(guide.get("imageUrls") or [])
        if not image_urls:
            return

        Thread = _real_thread()
        Thread(
            target=self._load_guide_image,
            args=(generation, payload, image_urls, duration),
            daemon=True,
        ).start()

    def hide_guide(self):
        self._guide_generation += 1
        self.start()
        self._q.put(("hide", None, 0))

    def _load_guide_image(self, generation, payload, image_urls, duration):
        cache_key = tuple(image_urls)
        cached_image = self._guide_image_cache.get(cache_key, "missing")
        if cached_image != "missing":
            if cached_image and generation == self._guide_generation:
                updated_guide = dict(payload["guide"])
                updated_guide["imageBytes"] = cached_image
                self._q.put(("show", {"guide": updated_guide}, duration))
            return

        try:
            import requests

            for image_url in image_urls:
                if generation != self._guide_generation:
                    return
                try:
                    response = requests.get(
                        image_url,
                        timeout=(1.5, 3.0),
                        headers={"User-Agent": "SolRich-Calibration-Guide"},
                    )
                    if response.status_code != 200:
                        continue
                    image_bytes = response.content
                    if not image_bytes or len(image_bytes) > 8 * 1024 * 1024:
                        continue
                    if generation != self._guide_generation:
                        return
                    self._guide_image_cache[cache_key] = image_bytes
                    updated_guide = dict(payload["guide"])
                    updated_guide["imageBytes"] = image_bytes
                    self._q.put(("show", {"guide": updated_guide}, duration))
                    return
                except requests.RequestException:
                    continue
            self._guide_image_cache[cache_key] = None
        except Exception as error:
            print(f"[Overlay] Calibration image load failed: {error}")

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
            root.update_idletasks()
            _make_click_through(root)

            state = {"hide_after": None, "images": []}

            def draw_guide(guide):
                if not isinstance(guide, dict):
                    return

                state["images"] = []
                anchor_rect = guide.get("anchorRect")
                if not (
                    isinstance(anchor_rect, (list, tuple))
                    and len(anchor_rect) == 4
                ):
                    anchor_rect = (vx, vy, vw, vh)

                window_x, window_y, window_width, window_height = (
                    int(value) for value in anchor_rect
                )
                panel_width = max(330, min(430, int(window_width * 0.24)))
                image_bytes = guide.get("imageBytes")
                panel_height = 380 if image_bytes else 180
                margin = max(18, min(32, int(window_width * 0.015)))
                panel_x = window_x + window_width - panel_width - margin - vx
                panel_y = (
                    window_y
                    + max(80, (window_height - panel_height) // 2)
                    - vy
                )
                panel_x = max(8, min(vw - panel_width - 8, panel_x))
                panel_y = max(8, min(vh - panel_height - 8, panel_y))
                panel_right = panel_x + panel_width
                panel_bottom = panel_y + panel_height

                canvas.create_rectangle(
                    panel_x,
                    panel_y,
                    panel_right,
                    panel_bottom,
                    fill="#16171e",
                    outline="#292a32",
                    width=1,
                )

                content_x = panel_x + 22
                content_width = panel_width - 44
                canvas.create_text(
                    content_x,
                    panel_y + 22,
                    text=str(guide.get("progress") or "CALIBRATION"),
                    anchor="nw",
                    fill="#6d84eb",
                    font=("Segoe UI", 9, "bold"),
                )
                canvas.create_text(
                    content_x,
                    panel_y + 47,
                    text=str(guide.get("title") or "Calibration"),
                    anchor="nw",
                    fill="#e8e9ee",
                    font=("Segoe UI", 17, "bold"),
                    width=content_width,
                )
                canvas.create_text(
                    content_x,
                    panel_y + 92,
                    text=str(guide.get("instruction") or "Click the target."),
                    anchor="nw",
                    fill="#e8e9ee",
                    font=("Segoe UI", 11, "bold"),
                    width=content_width,
                )

                if not image_bytes:
                    return

                try:
                    from io import BytesIO
                    from PIL import Image, ImageTk

                    image = Image.open(BytesIO(image_bytes)).convert("RGB")
                    image.thumbnail((content_width, 190), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    state["images"].append(photo)
                    image_x = panel_x + (panel_width - image.width) // 2
                    image_y = panel_y + 168
                    canvas.create_rectangle(
                        image_x - 2,
                        image_y - 2,
                        image_x + image.width + 2,
                        image_y + image.height + 2,
                        fill="#08090d",
                        outline="#343847",
                        width=1,
                    )
                    canvas.create_image(
                        image_x,
                        image_y,
                        image=photo,
                        anchor="nw",
                    )
                except Exception as error:
                    print(f"[Overlay] Calibration image decode failed: {error}")

            def draw(payload):
                canvas.delete("all")
                if isinstance(payload, dict):
                    points = payload.get("points", []) or []
                    regions = payload.get("regions", []) or []
                    guide = payload.get("guide")
                else:
                    points = payload or []
                    regions = []
                    guide = None
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
                draw_guide(guide)
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
                state["images"] = []
                try:
                    root.withdraw()
                except Exception:
                    pass

            def poll():
                try:
                    while True:
                        command, payload, duration = self._q.get_nowait()
                        if command == "hide":
                            hide()
                            continue
                        draw(payload)
                        _make_click_through(root)
                        root.deiconify()
                        root.lift()
                        root.attributes("-topmost", True)
                        if state["hide_after"] is not None:
                            try:
                                root.after_cancel(state["hide_after"])
                            except Exception:
                                pass
                        state["hide_after"] = None
                        if duration is not None:
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
        safe_duration = None if duration is None else float(duration)
        _OVERLAY.show({"points": pts, "regions": rgns}, safe_duration)
        return {"ok": True, "count": len(pts) + len(rgns)}
    except Exception as e:
        print(f"[Overlay] show failed: {e}")
        return {"ok": False, "error": "show_failed"}


def hide_points():
    
    if not IS_WINDOWS:
        return {"ok": False, "error": "not_windows"}
    try:
        _OVERLAY.hide_guide()
        return {"ok": True}
    except Exception as error:
        print(f"[Overlay] hide failed: {error}")
        return {"ok": False, "error": "hide_failed"}


def show_calibration_guide(guide, duration=None):
    
    if not IS_WINDOWS:
        return {"ok": False, "error": "not_windows"}
    if not isinstance(guide, dict) or not guide.get("title"):
        return {"ok": False, "error": "bad_guide"}
    try:
        safe_duration = (
            None
            if duration is None
            else max(2.0, min(65.0, float(duration)))
        )
        from . import calibration_web_overlay

        if calibration_web_overlay.show_guide(guide, safe_duration):
            return {"ok": True, "renderer": "css"}



        _OVERLAY.show_guide(guide, safe_duration)
        return {"ok": True, "renderer": "canvas_fallback"}
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad_duration"}
    except Exception as error:
        print(f"[Overlay] Calibration guide failed: {error}")
        return {"ok": False, "error": "show_failed"}


def hide_calibration_guide():
    if not IS_WINDOWS:
        return
    try:
        from . import calibration_web_overlay

        calibration_web_overlay.hide_guide()
    except Exception:
        pass
    _OVERLAY.hide_guide()
