

import html
import json
import re
import sys
import threading


IS_WINDOWS = sys.platform == "win32"
OVERLAY_WIDTH = 440
OVERLAY_HEIGHT = 480
OVERLAY_COMPACT_HEIGHT = 180
OVERLAY_MIN_HEIGHT = 150
TRANSPARENT_KEY = "#010203"
TRANSPARENT_COLORREF = 0x030201


def _build_html(guide):
    title = html.escape(str(guide.get("title") or "Calibration"))
    progress = html.escape(str(guide.get("progress") or "CALIBRATION"))
    instruction = html.escape(
        str(guide.get("instruction") or "Click the exact target once.")
    )
    image_urls = json.dumps(list(guide.get("imageUrls") or []))
    accent = str(guide.get("accent") or "#6d84eb")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        accent = "#6d84eb"
    accent_value = int(accent[1:], 16)
    accent_rgb = (
        (accent_value >> 16) & 255,
        (accent_value >> 8) & 255,
        accent_value & 255,
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      color-scheme: dark;
      --accent: {accent};
      --accent-rgb: {accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]};
      --text: #e8e9ee;
      --text-dim: #9b9ea9;
      --text-faint: #696c78;
      --stroke: rgba(255, 255, 255, 0.08);
      --surface: rgba(22, 23, 30, 0.94);
      --surface-soft: rgba(25, 26, 34, 0.94);
      --surface-strong: rgba(19, 20, 25, 0.96);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: {TRANSPARENT_KEY} !important;
      pointer-events: none !important;
      user-select: none;
      font-family: Inter, "Segoe UI Variable", "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    body {{
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0;
    }}
    .guide {{
      position: relative;
      width: 100%;
      overflow: hidden;
      padding: 18px;
      border: 1px solid var(--stroke);
      border-radius: 10px;
      background: var(--surface);
      animation: enter 140ms cubic-bezier(.4,0,.2,1) both;
    }}
    .topline {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 13px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      color: var(--accent);
      font-size: 11px;
      line-height: 1;
      font-weight: 750;
      letter-spacing: .11em;
      text-transform: uppercase;
    }}
    .eyebrow::before {{
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--accent);
    }}
    .pass-through {{
      color: var(--text-faint);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .02em;
    }}
    h1 {{
      margin: 0;
      color: var(--text);
      font-size: 18px;
      line-height: 1.3;
      font-weight: 700;
      letter-spacing: -0.015em;
    }}
    .instruction {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 14px;
      min-height: 42px;
      padding: 10px 12px;
      border: 1px solid var(--stroke);
      border-radius: 8px;
      background: var(--surface-soft);
      color: var(--text);
      font-size: 12px;
      line-height: 1.35;
      font-weight: 650;
    }}
    .target {{
      position: relative;
      width: 18px;
      height: 18px;
      flex: 0 0 18px;
      border: 1.5px solid var(--accent);
      border-radius: 50%;
    }}
    .target::before,
    .target::after {{
      content: "";
      position: absolute;
      background: var(--accent);
    }}
    .target::before {{ width: 8px; height: 1px; left: 4px; top: 7px; }}
    .target::after {{ width: 1px; height: 8px; left: 7px; top: 4px; }}
    figure {{
      display: none;
      margin: 14px 0 0;
      padding: 7px;
      border: 1px solid var(--stroke);
      border-radius: 8px;
      background: var(--surface-strong);
    }}
    figure.ready {{ display: block; }}
    figure img {{
      display: block;
      width: 100%;
      max-height: 190px;
      border-radius: 6px;
      object-fit: contain;
      background: rgba(0, 0, 0, 0.22);
    }}
    figcaption {{
      padding: 7px 3px 1px;
      color: var(--text-faint);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: .04em;
      text-transform: uppercase;
    }}
    @keyframes enter {{
      from {{ opacity: 0; transform: translateY(4px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
  </style>
</head>
<body>
  <main class="guide">
    <div class="topline">
      <span class="eyebrow">{progress}</span>
      <span class="pass-through">Click-through guide</span>
    </div>
    <h1>{title}</h1>
    <div class="instruction"><span class="target"></span><span>{instruction}</span></div>
    <figure id="reference">
      <img id="reference-image" alt="Calibration reference">
      <figcaption>Reference image</figcaption>
    </figure>
  </main>
  <script>
    const candidates = {image_urls};
    const figure = document.getElementById('reference');
    const image = document.getElementById('reference-image');
    let candidateIndex = 0;
    function loadNext() {{
      if (candidateIndex >= candidates.length) {{
        figure.classList.remove('ready');
        return;
      }}
      image.src = candidates[candidateIndex++];
    }}
    function reportHeight() {{
      requestAnimationFrame(() => {{
        const guide = document.querySelector('.guide');
        const desiredHeight = Math.ceil(guide?.getBoundingClientRect().height || 0);
        window.pywebview?.api?.set_height?.(desiredHeight);
      }});
    }}
    image.addEventListener('load', () => {{
      figure.classList.add('ready');
      reportHeight();
    }});
    image.addEventListener('error', () => {{
      loadNext();
      reportHeight();
    }});
    window.addEventListener('pywebviewready', reportHeight);
    window.setTimeout(reportHeight, 80);
    window.setTimeout(reportHeight, 300);
    loadNext();
  </script>
</body>
</html>"""


def _placement(guide, height=OVERLAY_HEIGHT):
    anchor_rect = guide.get("anchorRect")
    if not (
        isinstance(anchor_rect, (list, tuple))
        and len(anchor_rect) == 4
    ):
        anchor_rect = (0, 0, 1920, 1080)

    window_x, window_y, window_width, window_height = (
        int(value) for value in anchor_rect
    )
    margin = max(18, min(32, int(window_width * 0.015)))
    x = window_x + window_width - OVERLAY_WIDTH - margin
    y = window_y + max(70, (window_height - int(height)) // 2)
    return x, y


def _make_click_through(window):
    if not IS_WINDOWS or window is None or window.native is None:
        return False
    try:
        import ctypes

        native_handle = window.native.Handle
        hwnd = int(native_handle.ToInt64())
        user32 = ctypes.windll.user32
        extended_style = user32.GetWindowLongW(hwnd, -20)
        extended_style |= 0x00080000
        extended_style |= 0x00000020
        extended_style |= 0x00000080
        extended_style |= 0x08000000
        user32.SetWindowLongW(hwnd, -20, extended_style)




        transparent_background = user32.SetLayeredWindowAttributes(
            ctypes.c_void_p(hwnd),
            TRANSPARENT_COLORREF,
            0,
            0x00000001,
        )
        if not transparent_background:
            raise ctypes.WinError()
        user32.SetWindowPos(
            hwnd,
            -1,
            0,
            0,
            0,
            0,
            0x0001 | 0x0002 | 0x0010,
        )
        return True
    except Exception as error:
        print(f"[CalibrationOverlay] Could not enable click-through: {error}")
        return False


class _GuideWindowApi:
    def __init__(self, overlay):
        self._overlay = overlay

    def set_height(self, height):
        return self._overlay.resize_to_content(height)


class _CalibrationWebOverlay:
    def __init__(self):
        self._window = None
        self._generation = 0
        self._lock = threading.Lock()
        self._guide = None

    def resize_to_content(self, height):
        try:
            target_height = max(
                OVERLAY_MIN_HEIGHT,
                min(OVERLAY_HEIGHT, int(round(float(height)))),
            )
        except (TypeError, ValueError):
            return False

        with self._lock:
            window = self._window
            guide = self._guide
            if window is None or guide is None:
                return False
            x, y = _placement(guide, height=target_height)
            try:
                window.resize(OVERLAY_WIDTH, target_height)
                window.move(x, y)
                _make_click_through(window)
                return True
            except Exception as error:
                print(f"[CalibrationOverlay] Could not resize guide: {error}")
                return False

    def show(self, guide, duration):
        if not IS_WINDOWS:
            return False
        try:
            import webview

            if not getattr(webview, "guilib", None):
                return False

            page = _build_html(guide)
            initial_height = OVERLAY_COMPACT_HEIGHT
            x, y = _placement(guide, height=initial_height)
            with self._lock:
                self._generation += 1
                generation = self._generation
                self._guide = dict(guide)

                if self._window is None or self._window.native is None:
                    created_window = webview.create_window(
                        "SolRich Calibration Guide",
                        html=page,
                        js_api=_GuideWindowApi(self),
                        width=OVERLAY_WIDTH,
                        height=initial_height,
                        x=x,
                        y=y,
                        resizable=False,
                        frameless=True,
                        easy_drag=False,
                        shadow=False,
                        focus=False,
                        on_top=True,
                        background_color=TRANSPARENT_KEY,
                        transparent=True,
                        text_select=False,
                        zoomable=False,
                    )
                    self._window = created_window
                    created_window.events.shown += (
                        lambda *_args: _make_click_through(created_window)
                    )
                else:
                    self._window.load_html(page)
                    self._window.resize(OVERLAY_WIDTH, initial_height)
                    self._window.move(x, y)
                    self._window.show()

                if self._window is None:
                    return False
                _make_click_through(self._window)

            if duration is not None:
                timer = threading.Timer(
                    max(2.0, float(duration)),
                    self._hide_generation,
                    args=(generation,),
                )
                timer.daemon = True
                timer.start()
            return True
        except Exception as error:
            print(f"[CalibrationOverlay] CSS overlay unavailable: {error}")
            return False

    def _hide_generation(self, generation):
        with self._lock:
            if generation != self._generation:
                return
        self.hide()

    def hide(self):
        with self._lock:
            self._generation += 1
            window = self._window




            self._window = None
            self._guide = None
        if window is None:
            return
        try:
            window.destroy()
        except Exception as error:
            print(f"[CalibrationOverlay] Could not destroy guide window: {error}")


_OVERLAY = _CalibrationWebOverlay()


def show_guide(guide, duration=None):
    return _OVERLAY.show(guide, duration)


def hide_guide():
    _OVERLAY.hide()
