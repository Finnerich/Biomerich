import os
import re
import sys
import time
import random
import threading
import urllib.parse

import requests

from .roblox_tray_cleanup import cleanup as _tray_cleanup
from . import roblox_guard as _detached_guard

IS_WINDOWS = sys.platform == "win32"

SOLS_PLACE_ID = 15532962292

_USER_AGENT = "Roblox/WinInet"
_BASE_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.roblox.com/",
    "Origin": "https://www.roblox.com",
}

_MULTI_INSTANCE_MUTEX = "ROBLOX_singletonMutex"
_ERROR_ALREADY_EXISTS = 183
_mutex_handles = []
_mutex_lock = threading.RLock()
_mutex_guard_thread = None
_mutex_guard_stop = None
_mutex_guard_initialized = None
_mutex_guard_owns = False

def _cookie_header(token):
    return {"Cookie": f".ROBLOSECURITY={token}"}

def mask_token(token):
    if not token:
        return ""
    return "•" * 12

def _refreshed_cookie(resp, sent_token):
    
    try:
        for c in resp.cookies:
            if c.name != ".ROBLOSECURITY":
                continue
            new = (c.value or "").strip()
            if len(new) >= 100 and "WARNING" in new and new != (sent_token or "").strip():
                return new
    except Exception:
        pass
    return ""

def validate_token(token):
    
    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "empty", "definitive": True, "refreshed": ""}
    try:
        r = requests.get(
            "https://users.roblox.com/v1/users/authenticated",
            headers={**_BASE_HEADERS, **_cookie_header(token)},
            timeout=12,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"network: {e}", "definitive": False, "refreshed": ""}

    refreshed = _refreshed_cookie(r, token)
    if r.status_code == 401:
        return {"ok": False, "error": "invalid", "definitive": True, "refreshed": refreshed}
    if r.status_code != 200:
        return {"ok": False, "error": f"http_{r.status_code}", "definitive": False, "refreshed": refreshed}
    try:
        data = r.json()
    except ValueError:
        return {"ok": False, "error": "bad_response", "definitive": False, "refreshed": refreshed}
    return {
        "ok": True,
        "id": data.get("id"),
        "name": data.get("name", ""),
        "displayName": data.get("displayName", ""),
        "definitive": True,
        "refreshed": refreshed,
    }

def _csrf(token):
    try:
        r = requests.post(
            "https://auth.roblox.com/v1/authentication-ticket/",
            headers={**_BASE_HEADERS, **_cookie_header(token)},
            timeout=12,
        )
        return r.headers.get("x-csrf-token", "")
    except requests.RequestException:
        return ""

_last_ticket_error = ""
_last_refreshed_cookie = ""

def get_auth_ticket(token):
    global _last_ticket_error, _last_refreshed_cookie
    _last_ticket_error = ""
    _last_refreshed_cookie = ""

    url = "https://auth.roblox.com/v1/authentication-ticket/"
    headers = {
        **_BASE_HEADERS,
        **_cookie_header(token),
        "RBXAuthenticationNegotiation": "1",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(url, headers=headers, timeout=12)
    except requests.RequestException as e:
        _last_ticket_error = f"network: {e}"
        return ""

    for _ in range(3):
        ref = _refreshed_cookie(r, token)
        if ref:
            _last_refreshed_cookie = ref
        ticket = r.headers.get("rbx-authentication-ticket", "")
        if ticket:
            return ticket
        csrf = r.headers.get("x-csrf-token", "")
        if not csrf:
            _last_ticket_error = f"http_{r.status_code}"
            return ""
        headers["X-CSRF-TOKEN"] = csrf
        try:
            r = requests.post(url, headers=headers, timeout=12)
        except requests.RequestException as e:
            _last_ticket_error = f"network: {e}"
            return ""

    ref = _refreshed_cookie(r, token)
    if ref:
        _last_refreshed_cookie = ref
    ticket = r.headers.get("rbx-authentication-ticket", "")
    if not ticket:
        _last_ticket_error = f"http_{r.status_code}"
    return ticket

_share_cache = {}

def _resolve_share_link(token, code):
    cached = _share_cache.get(code)
    if cached:
        return cached
    csrf = _csrf(token)
    headers = {**_BASE_HEADERS, **_cookie_header(token), "X-CSRF-TOKEN": csrf,
               "Content-Type": "application/json"}
    try:
        r = requests.post(
            "https://apis.roblox.com/sharelinks/v1/resolve-link",
            headers=headers,
            json={"linkId": code, "linkType": "Server"},
            timeout=12,
        )
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    invite = data.get("privateServerInviteData") or {}
    place_id = invite.get("placeId")
    if not place_id:
        return None
    info = {
        "placeId": place_id,
        "linkCode": invite.get("linkCode"),
        "accessCode": invite.get("accessCode"),
    }
    _share_cache[code] = info
    return info

def parse_private_link(token, link):
    link = (link or "").strip()
    if not link:
        return None

    place_match = re.search(r"/games/(\d+)", link)
    link_code = None
    access_code = None

    m = re.search(r"privateServerLinkCode=([^&]+)", link)
    if m:
        link_code = m.group(1)
    m = re.search(r"accessCode=([^&]+)", link)
    if m:
        access_code = m.group(1)

    if place_match:
        return {
            "placeId": int(place_match.group(1)),
            "linkCode": link_code,
            "accessCode": access_code,
        }

    m = re.search(r"[?&]code=([^&]+)", link)
    if m:
        return _resolve_share_link(token, m.group(1))

    return None

def _place_launcher_url(place_info):
    btid = random.randint(100000, 99999999)
    base = "https://assetgame.roblox.com/game/PlaceLauncher.ashx"
    place_id = place_info.get("placeId")
    if place_info.get("linkCode"):
        params = {
            "request": "RequestPrivateGame",
            "browserTrackerId": btid,
            "placeId": place_id,
            "linkCode": place_info["linkCode"],
        }
    elif place_info.get("accessCode"):
        params = {
            "request": "RequestPrivateGame",
            "browserTrackerId": btid,
            "placeId": place_id,
            "accessCode": place_info["accessCode"],
        }
    else:
        params = {
            "request": "RequestGame",
            "browserTrackerId": btid,
            "placeId": place_id,
            "isPlayTogetherGame": "false",
        }
    return base + "?" + urllib.parse.urlencode(params), btid

def _create_multi_instance_mutex():
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, True, _MULTI_INSTANCE_MUTEX)
    return handle, ctypes.get_last_error() == _ERROR_ALREADY_EXISTS


def _mutex_guard_worker(stop_event, initialized_event):
    
    global _mutex_guard_owns
    import ctypes
    from ctypes import wintypes

    wait_object = 0x00000000
    wait_abandoned = 0x00000080
    wait_timeout_ms = 200
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel32.ReleaseMutex.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = None
    owns_mutex = False
    try:
        handle, already_exists = _create_multi_instance_mutex()
        if not handle:
            initialized_event.set()
            return




        if not already_exists:
            owns_mutex = True
        else:
            wait_result = kernel32.WaitForSingleObject(handle, 0)
            owns_mutex = wait_result in (wait_object, wait_abandoned)

        with _mutex_lock:
            _mutex_handles.append(handle)
            _mutex_guard_owns = owns_mutex
        initialized_event.set()

        while not stop_event.is_set():
            if owns_mutex:
                stop_event.wait(0.2)
                continue
            wait_result = kernel32.WaitForSingleObject(handle, wait_timeout_ms)
            if wait_result in (wait_object, wait_abandoned):
                owns_mutex = True
                with _mutex_lock:
                    _mutex_guard_owns = True
    finally:
        if not initialized_event.is_set():
            initialized_event.set()
        if handle:
            if owns_mutex:
                try:
                    kernel32.ReleaseMutex(handle)
                except Exception:
                    pass
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
        with _mutex_lock:
            if handle in _mutex_handles:
                _mutex_handles.remove(handle)
            _mutex_guard_owns = False


def ensure_multi_instance():
    
    global _mutex_guard_thread, _mutex_guard_stop, _mutex_guard_initialized
    if not IS_WINDOWS:
        return False
    if _detached_guard.ensure():
        return True
    with _mutex_lock:
        if _mutex_guard_thread is not None and _mutex_guard_thread.is_alive():
            return bool(_mutex_guard_owns)
        stop_event = threading.Event()
        initialized_event = threading.Event()
        guard_thread = threading.Thread(
            target=_mutex_guard_worker,
            args=(stop_event, initialized_event),
            name="roblox-multi-instance-guard",
            daemon=True,
        )
        _mutex_guard_stop = stop_event
        _mutex_guard_initialized = initialized_event
        _mutex_guard_thread = guard_thread
        guard_thread.start()

    initialized_event.wait(0.75)
    with _mutex_lock:
        return bool(_mutex_guard_owns)

def _launch_protocol(ticket, place_launcher_url, btid):
    proto = (
        "roblox-player:1+launchmode:play"
        f"+gameinfo:{ticket}"
        f"+launchtime:{int(time.time() * 1000)}"
        f"+placelauncherurl:{urllib.parse.quote(place_launcher_url, safe='')}"
        f"+browsertrackerid:{btid}"
        "+robloxLocale:en_us+gameLocale:en_us+channel:"
    )
    if IS_WINDOWS:
        os.startfile(proto)
        return True
    return False

def _launch_home(ticket):
    btid = random.randint(100000, 99999999)
    proto = (
        "roblox-player:1+launchmode:app"
        f"+gameinfo:{ticket}"
        f"+launchtime:{int(time.time() * 1000)}"
        f"+browsertrackerid:{btid}"
        "+robloxLocale:en_us+gameLocale:en_us+channel:"
    )
    if IS_WINDOWS:
        os.startfile(proto)
        return True
    return False

def release_multi_instance(stop_detached=False):
    
    global _mutex_guard_thread, _mutex_guard_stop, _mutex_guard_initialized
    if not IS_WINDOWS:
        return
    if stop_detached:
        _detached_guard.request_stop()
    with _mutex_lock:
        stop_event = _mutex_guard_stop
        guard_thread = _mutex_guard_thread
    if stop_event is not None:
        stop_event.set()
    if guard_thread is not None and guard_thread.is_alive():
        guard_thread.join(timeout=2.0)
    with _mutex_lock:
        _mutex_guard_thread = None
        _mutex_guard_stop = None
        _mutex_guard_initialized = None


def _rearm_multi_instance_after_teleport():
    def rearm():
        time.sleep(1.5)
        ensure_multi_instance()
    threading.Thread(target=rearm, name="roblox-multi-rearm", daemon=True).start()

def teleport_in_place(place_info):
    
    place_id = place_info.get("placeId")
    if not place_id:
        return False
    release_multi_instance(stop_detached=True)
    link_code = place_info.get("linkCode")
    access_code = place_info.get("accessCode")
    if link_code:
        uri = f"roblox://experiences/start?placeId={place_id}&linkCode={link_code}"
    elif access_code:
        uri = f"roblox://experiences/start?placeId={place_id}&accessCode={access_code}"
    else:
        uri = f"roblox://experiences/start?placeId={place_id}"
    if IS_WINDOWS:
        os.startfile(uri)
        _rearm_multi_instance_after_teleport()
        return True
    return False

def launch_account(account, mode="home"):
    token = (account.get("token") or "").strip()
    if not token:
        return {"ok": False, "error": "no_token", "refreshed": ""}

    info = validate_token(token)
    refreshed = info.get("refreshed") or ""
    if not info.get("ok") and info.get("definitive"):
        return {"ok": False, "error": "token_" + str(info.get("error")), "refreshed": refreshed}

    if not IS_WINDOWS:
        return {"ok": False, "error": "not_windows", "refreshed": refreshed}

    if not ensure_multi_instance():
        return {
            "ok": False,
            "error": "multi_instance_guard_late",
            "refreshed": refreshed,
        }

    ticket = get_auth_ticket(token)
    if _last_refreshed_cookie:
        refreshed = _last_refreshed_cookie
    if not ticket:
        return {"ok": False, "error": "no_ticket:" + (_last_ticket_error or "unknown"), "refreshed": refreshed}

    name = info.get("name", "")

    if mode == "home":


        previous_roblox_pids = _tray_cleanup.process_snapshot()
        try:
            ok = _launch_home(ticket)
        except OSError as e:
            return {"ok": False, "error": f"launch_failed: {e}", "refreshed": refreshed}
        if ok:
            _tray_cleanup.register_launch(previous_roblox_pids)
        return {"ok": ok, "name": name, "refreshed": refreshed}

    if mode == "public":
        place_info = {"placeId": SOLS_PLACE_ID}
    else:
        place_info = parse_private_link(token, account.get("link"))
        if not place_info:
            return {"ok": False, "error": "bad_link", "refreshed": refreshed}

    url, btid = _place_launcher_url(place_info)
    previous_roblox_pids = _tray_cleanup.process_snapshot()
    try:
        ok = _launch_protocol(ticket, url, btid)
    except OSError as e:
        return {"ok": False, "error": f"launch_failed: {e}", "refreshed": refreshed}
    if ok:
        _tray_cleanup.register_launch(previous_roblox_pids)
    return {"ok": ok, "name": name, "refreshed": refreshed}


def stop_account_launch_cleanup():
    _tray_cleanup.stop()
