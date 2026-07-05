import os
import re
import sys
import time
import random
import urllib.parse

import requests

IS_WINDOWS = sys.platform == "win32"

SOLS_PLACE_ID = 15532962292

_USER_AGENT = "Roblox/WinInet"
_BASE_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.roblox.com/",
    "Origin": "https://www.roblox.com",
}

_mutex_handles = []

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

def ensure_multi_instance():
    if not IS_WINDOWS or _mutex_handles:
        return bool(_mutex_handles)
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    for name in ("ROBLOX_singletonMutex", "ROBLOX_singletonEvent"):
        handle = kernel32.CreateMutexW(None, False, name)
        if handle:
            _mutex_handles.append(handle)
    return bool(_mutex_handles)

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

def release_multi_instance():
    
    if not IS_WINDOWS or not _mutex_handles:
        return
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    for h in list(_mutex_handles):
        try:
            kernel32.CloseHandle(h)
        except Exception:
            pass
    _mutex_handles.clear()

def teleport_in_place(place_info):
    
    place_id = place_info.get("placeId")
    if not place_id:
        return False
    release_multi_instance()
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

    ensure_multi_instance()

    ticket = get_auth_ticket(token)
    if _last_refreshed_cookie:
        refreshed = _last_refreshed_cookie
    if not ticket:
        return {"ok": False, "error": "no_ticket:" + (_last_ticket_error or "unknown"), "refreshed": refreshed}

    name = info.get("name", "")

    if mode == "home":
        try:
            ok = _launch_home(ticket)
        except OSError as e:
            return {"ok": False, "error": f"launch_failed: {e}", "refreshed": refreshed}
        return {"ok": ok, "name": name, "refreshed": refreshed}

    if mode == "public":
        place_info = {"placeId": SOLS_PLACE_ID}
    else:
        place_info = parse_private_link(token, account.get("link"))
        if not place_info:
            return {"ok": False, "error": "bad_link", "refreshed": refreshed}

    url, btid = _place_launcher_url(place_info)
    try:
        ok = _launch_protocol(ticket, url, btid)
    except OSError as e:
        return {"ok": False, "error": f"launch_failed: {e}", "refreshed": refreshed}
    return {"ok": ok, "name": name, "refreshed": refreshed}
