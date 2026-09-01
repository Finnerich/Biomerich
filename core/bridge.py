import asyncio
import hmac
import json
import os
import socket
import threading
import subprocess
import sys
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse

from . import buildflag

_exposed: Dict[str, Callable] = {}
_web_root: Optional[str] = None
_app = FastAPI()
_loop: Optional[asyncio.AbstractEventLoop] = None
_clients: set = set()
_clients_lock = threading.Lock()
_desktop_clients = 0
_desktop_client_seen = threading.Event()
_desktop_clients_changed = threading.Event()
_pending_calls: list = []
_pending_lock = threading.Lock()

_rpc_executor = ThreadPoolExecutor(max_workers=24, thread_name_prefix="rpc")



def init(path: str):

    global _web_root
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _web_root = os.path.join(base, path)

def expose(fn=None, name: Optional[str] = None):

    if fn is None:

        def deco(f):
            _exposed[name or f.__name__] = f
            return f
        return deco
    _exposed[name or getattr(fn, "__name__", str(fn))] = fn
    return fn

class _JsProxy:

    def __init__(self, fn_name: str):
        self._fn_name = fn_name

    def __call__(self, *args):
        payload = {"type": "call", "name": self._fn_name, "args": list(args)}

        def _send():
            _broadcast(payload)

        return _send

def __getattr__(name: str):

    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(name)
    return _JsProxy(name)

def _broadcast(payload: dict):

    msg = json.dumps(payload)
    with _clients_lock:
        clients = list(_clients)
    if not clients or _loop is None:
        with _pending_lock:
            _pending_calls.append(msg)
        return
    for ws in clients:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), _loop)
        except Exception:
            pass

async def _handle_ws(
    ws: WebSocket,
    already_accepted: bool = False,
):
    
    global _desktop_clients
    desktop_client = True
    if not already_accepted:
        await ws.accept()
    with _clients_lock:
        _clients.add(ws)
    if desktop_client:
        with _clients_lock:
            _desktop_clients += 1
        _desktop_client_seen.set()
        _desktop_clients_changed.set()
    with _pending_lock:
        pending = list(_pending_calls)
        _pending_calls.clear()
    for msg in pending:
        try:
            await ws.send_text(msg)
        except Exception:
            pass
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            if data.get("type") == "rpc":
                call_id = data.get("id")
                fn_name = data.get("name")
                args = data.get("args", [])
                fn = _exposed.get(fn_name)
                result = None
                error = None
                if fn is None:
                    error = f"No exposed function '{fn_name}'"
                else:
                    try:

                        def _invoke(fn=fn, args=args):
                            try:
                                return fn(*args)
                            finally:
                                pass

                        result = await asyncio.get_event_loop().run_in_executor(
                            _rpc_executor, _invoke
                        )
                    except Exception as e:
                        error = str(e)
                        import traceback
                        traceback.print_exc()
                await ws.send_text(json.dumps({
                    "type": "rpc_result",
                    "id": call_id,
                    "result": result,
                    "error": error,
                }))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        with _clients_lock:
            _clients.discard(ws)
            if desktop_client:
                _desktop_clients = max(0, _desktop_clients - 1)
        if desktop_client:
            _desktop_clients_changed.set()

@_app.websocket("/ws")
async def _ws_endpoint(ws: WebSocket):
    await _handle_ws(ws)


@_app.get("/")
async def _root():
    return FileResponse(os.path.join(_web_root, "index.html"))

@_app.get("/eel.js")
async def _eel_js():

    return FileResponse(os.path.join(_web_root, "eel.js"),
                        media_type="application/javascript")

@_app.get("/{filepath:path}")
async def _static(filepath: str):

    if not filepath:
        return FileResponse(os.path.join(_web_root, "index.html"))
    full = os.path.abspath(os.path.join(_web_root, filepath))
    if not full.startswith(_web_root):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if os.path.isfile(full):
        return FileResponse(full)
    return JSONResponse({"error": "not found"}, status_code=404)

def _resolve_icon() -> str:
    
    if not _web_root:
        return ""
    ico = os.path.join(_web_root, "assets", "icon.ico")
    png = os.path.join(_web_root, "assets", "icon.png")
    if os.path.isfile(ico):
        return ico
    if not os.path.isfile(png):
        return ""
    try:
        from PIL import Image
        img = Image.open(png)
        img.save(ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        return ico
    except Exception:
        return png

def _apply_native_window_icon(pid: int, ico_path: str):
    
    if sys.platform != "win32" or not ico_path or not os.path.isfile(ico_path):
        return
    try:
        import time
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        WM_SETICON, ICON_SMALL, ICON_BIG, IMAGE_ICON, LR_LOADFROMFILE = 0x0080, 0, 1, 1, 0x0010
        u.LoadImageW.restype = wintypes.HANDLE
        u.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT)
        u.SendMessageW.restype = ctypes.c_long
        u.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        u.IsWindowVisible.argtypes = (wintypes.HWND,)
        u.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
        EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        h_big = u.LoadImageW(None, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
        h_small = u.LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        if not h_big and not h_small:
            return

        def our_windows():
            found = []

            def cb(hwnd, _lparam):
                wpid = wintypes.DWORD()
                u.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
                if wpid.value == pid and u.IsWindowVisible(hwnd) and u.GetWindowTextLengthW(hwnd) > 0:
                    found.append(hwnd)
                return True

            u.EnumWindows(EnumProc(cb), 0)
            return found

        deadline = time.monotonic() + 8.0
        seen = False
        while time.monotonic() < deadline:
            wins = our_windows()
            for hwnd in wins:
                if h_big:
                    u.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
                if h_small:
                    u.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
                seen = True
            time.sleep(0.5 if seen else 0.25)
    except Exception:
        pass


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_for_server_start(server, server_thread, timeout: float = 5.0) -> bool:
    
    deadline = time.monotonic() + max(0.0, float(timeout))
    while time.monotonic() < deadline:
        if bool(getattr(server, "started", False)):
            return True
        if not server_thread.is_alive():
            return False
        time.sleep(0.05)
    return bool(getattr(server, "started", False))

_browser_proc = None

def close_app():
    
    proc = _browser_proc
    if proc is None:
        return False
    try:
        proc.terminate()
        return True
    except Exception:
        return False

def _launch_browser(url: str, mode: str, profile_dir: str, debug: bool = False):

    global _browser_proc
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    candidates = []
    if mode == "chrome":
        candidates = chrome_paths
    elif mode == "edge":
        candidates = edge_paths

    for exe in candidates:
        if os.path.isfile(exe):
            icon_path = _resolve_icon()
            args = [
                exe,
                f"--app={url}",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--new-window",
                "--window-size=1100,700",
            ]
            if icon_path:
                args.append(f"--app-icon={icon_path}")
            if debug:

                args.append("--auto-open-devtools-for-tabs")
            try:
                _browser_proc = subprocess.Popen(args)
                if icon_path:
                    threading.Thread(
                        target=_apply_native_window_icon,
                        args=(_browser_proc.pid, icon_path),
                        daemon=True,
                    ).start()
                return True
            except Exception:
                continue
    if mode == "default":
        webbrowser.open(url)
        return True
    return False


def _log_ui_fallback(reason: str):
    
    try:
        from .config import get_config_dir
        with open(os.path.join(get_config_dir(), "ui_launch.log"), "w", encoding="utf-8") as fh:
            fh.write(f"Native window failed, used browser fallback.\nReason: {reason}\n")
    except Exception:
        pass


def _clear_ui_fallback_log():
    try:
        from .config import get_config_dir
        p = os.path.join(get_config_dir(), "ui_launch.log")
        if os.path.isfile(p):
            os.remove(p)
    except Exception:
        pass


def _open_native_window(
    url: str,
    size,
    debug: bool = False,
    on_closed=None,
    storage_path: Optional[str] = None,
    load_timeout: float = 8.0,
) -> bool:
    
    _clear_ui_fallback_log()
    try:
        import webview
    except Exception as e:
        _log_ui_fallback(f"pywebview not bundled / import failed: {e}")
        return False
    loaded = threading.Event()
    load_failed = threading.Event()
    try:
        w, h = size or (1080, 720)
        main_window = webview.create_window(
            "SolRich",
            url,
            width=int(w),
            height=int(h),
            min_size=(940, 640),
        )
        if hasattr(main_window.events, "loaded"):
            def _handle_loaded(*_args):
                loaded.set()

            main_window.events.loaded += _handle_loaded
        else:


            loaded.set()
        if callable(on_closed):
            def _handle_closed(*_args):
                try:
                    on_closed()
                except Exception as error:
                    print(f"[Bridge] UI close cleanup failed: {error}")

            main_window.events.closed += _handle_closed
    except Exception as e:
        print(f"[Bridge] Native window unavailable ({e}); falling back to browser.")
        _log_ui_fallback(f"create_window failed: {e}")
        return False
    ico = _resolve_icon()
    if ico:

        threading.Thread(target=_apply_native_window_icon, args=(os.getpid(), ico), daemon=True).start()





    def _load_watchdog():
        if loaded.wait(max(0.05, float(load_timeout))):
            return
        load_failed.set()
        _log_ui_fallback(
            f"native window did not finish loading within {float(load_timeout):g} seconds"
        )
        try:
            main_window.destroy()
        except Exception as error:
            print(f"[Bridge] Could not close failed native window: {error}")

    threading.Thread(
        target=_load_watchdog,
        name="native-ui-load-watchdog",
        daemon=True,
    ).start()
    try:
        start_options = {"debug": debug, "private_mode": False}
        if storage_path:
            start_options["storage_path"] = storage_path
        webview.start(**start_options)
        if load_failed.is_set() or not loaded.is_set():
            print("[Bridge] Native window never loaded; falling back to browser.")
            return False
        return True
    except Exception as e:
        print(f"[Bridge] Native window failed to start ({e}); falling back to browser.")
        _log_ui_fallback(f"webview.start failed: {e}")
        return False


def start(page: str, size=None, mode: str = "chrome",
          cmdline_args=None, port: int = 0,
          open_url: Optional[str] = None, debug: bool = False,
          on_close=None,
          **kwargs):

    global _loop

    if port == 0:
        port = _find_free_port()



    url = open_url or f"http://127.0.0.1:{port}/"

    profile_dir = os.path.join(
        os.getenv("LOCALAPPDATA") or os.path.expanduser("~"),
        "SolRich", "web_profile",
    )
    if cmdline_args:
        for a in cmdline_args:
            if a.startswith("--user-data-dir="):
                profile_dir = a.split("=", 1)[1]

    config = uvicorn.Config(_app, host="127.0.0.1", port=port,
                            log_level="warning", loop="asyncio",
                            log_config=None)
    server = uvicorn.Server(config)

    async def _serve():
        global _loop
        _loop = asyncio.get_event_loop()
        desktop_task = asyncio.ensure_future(server.serve())
        await desktop_task



    server_thread = threading.Thread(target=lambda: asyncio.run(_serve()), daemon=True)
    server_thread.start()

    if not _wait_for_server_start(server, server_thread):
        server.should_exit = True
        server_thread.join(timeout=1)
        raise EnvironmentError(
            f"SolRich backend could not start on 127.0.0.1:{port}. "
            "Another SolRich instance may already be running."
        )




    ui_ok = _open_native_window(
        url,
        size,
        debug=debug,
        on_closed=on_close,
        storage_path=os.path.join(os.path.dirname(profile_dir), "native_webview_profile"),
    )
    if not ui_ok:
        _desktop_client_seen.clear()
        _desktop_clients_changed.clear()
        if _launch_browser(url, mode, profile_dir, debug=debug):
            _watch_browser(server)
            ui_ok = True
        else:
            print(f"[Bridge] Could not launch the UI in '{mode}' mode")




    if callable(on_close):
        try:
            on_close()
        except Exception as error:
            print(f"[Bridge] UI close cleanup failed: {error}")

    if _loop is not None:
        _loop.call_soon_threadsafe(lambda: setattr(server, "should_exit", True))
    else:
        server.should_exit = True
    server_thread.join(timeout=5)

    if not ui_ok:
        raise EnvironmentError(f"Could not launch the UI in '{mode}' mode")

def _watch_browser(server, connect_timeout: float = 20.0, disconnect_grace: float = 1.5):
    
    if not _desktop_client_seen.wait(max(0.1, float(connect_timeout))):
        print("[Bridge] Browser UI did not connect in time — shutting down.")
        server.should_exit = True
        return

    disconnected_at = None
    grace = max(0.1, float(disconnect_grace))
    while True:
        with _clients_lock:
            connected = _desktop_clients > 0
        if connected:
            disconnected_at = None
        elif disconnected_at is None:
            disconnected_at = time.monotonic()
        elif time.monotonic() - disconnected_at >= grace:
            break

        _desktop_clients_changed.wait(0.25)
        _desktop_clients_changed.clear()

    server.should_exit = True
    print("[Bridge] Browser UI disconnected — shutting down.")
