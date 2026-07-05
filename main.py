import webbrowser

from core import bridge as eel

import os
import sys
import time
import threading





if sys.platform == "win32":
    import subprocess as _subprocess
    _CREATE_NO_WINDOW = 0x08000000
    _orig_popen_init = _subprocess.Popen.__init__
    def _quiet_popen_init(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = _CREATE_NO_WINDOW
        _orig_popen_init(self, *args, **kwargs)
    _subprocess.Popen.__init__ = _quiet_popen_init

try:
    import keyboard
    _KEYBOARD_AVAILABLE = True
except ImportError:
    _KEYBOARD_AVAILABLE = False
    print("[Hotkey] 'keyboard' module not found. Install with: pip install keyboard")

from core import ConfigManager, MacroEngine, updater, presets
from core import fishing_presets
from core import overlay
from core import status_events
from core import creator
from core import roblox_auth
from core import perf as perfmon
from core import ram_trim
from core import throttle as throttle_mod
from core import browser_login as browser_login_mod
from core import presets as _auto_presets
from core import fishing_presets as _fish_presets
from core import ocr

def _maybe_relaunch_deelevated():
    
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return
    except Exception:
        return
    try:
        import ctypes
        exe = sys.executable
        print("[SolRich] Started as administrator — relaunching without elevation "
              "so the window renders (admin isn't needed).")
        ctypes.windll.shell32.ShellExecuteW(None, "open", "explorer.exe", f'"{exe}"', None, 1)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[SolRich] Could not de-elevate ({e}); continuing as administrator.")

_maybe_relaunch_deelevated()

eel.init(os.environ.get("SOLRICH_WEB") or os.environ.get("BIOMERICH_WEB", "web-react-dist"))

config = ConfigManager()
try:
    from core import applog as _applog
    _applog.setup(config.dir)
except Exception:
    pass
engine = MacroEngine(config)
ram_trimmer = ram_trim.RamTrimmer(config, is_engine_running=lambda: engine.running)
throttler = throttle_mod.ThrottleEngine(config, is_engine_running=lambda: engine.running)

browser_login = browser_login_mod.BrowserLogin()

import atexit as _atexit
from core import webhooks as _webhooks
_atexit.register(throttler.stop)
_atexit.register(browser_login.cancel)
_atexit.register(lambda: _webhooks.flush(8.0))
_atexit.register(config.save_now)


_hotkey_handle = None
_hotkey_lock = threading.Lock()

_mode_hotkey_handle = None
_mode_hotkey_lock = threading.Lock()

def _on_mode_hotkey_triggered():
    order = ("idle", "automation", "eden")
    cur = config.automation.get("mode", "idle")
    try:
        next_mode = order[(order.index(cur) + 1) % len(order)]
    except ValueError:
        next_mode = "automation"
    engine.set_automation_mode(next_mode)
    eel.js_on_mode_hotkey(next_mode)()

def _register_mode_hotkey(key: str):
    global _mode_hotkey_handle
    if not _KEYBOARD_AVAILABLE:
        return
    with _mode_hotkey_lock:
        if _mode_hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(_mode_hotkey_handle)
            except Exception:
                pass
            _mode_hotkey_handle = None
        if not key or key.lower() == "none":
            return
        try:
            _mode_hotkey_handle = keyboard.add_hotkey(key, _on_mode_hotkey_triggered, suppress=True)
            print(f"[Hotkey] Registered mode toggle hotkey: {key}")
        except Exception as e:
            print(f"[Hotkey] Could not register mode hotkey '{key}': {e}")

def _on_hotkey_triggered():
    if engine.running:
        result = engine.stop()
        eel.js_on_hotkey_stop(result)()
    else:
        result = engine.start()
        eel.js_on_hotkey_start(result)()

def _register_hotkey(key: str):
    global _hotkey_handle
    if not _KEYBOARD_AVAILABLE:
        return
    with _hotkey_lock:
        if _hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(_hotkey_handle)
            except Exception:
                pass
            _hotkey_handle = None
        try:
            _hotkey_handle = keyboard.add_hotkey(key, _on_hotkey_triggered, suppress=True)
            print(f"[Hotkey] Registered global hotkey: {key}")
        except Exception as e:
            print(f"[Hotkey] Could not register '{key}': {e}")

def _state_with_status() -> dict:
    state = config.state()
    state["running"] = engine.running
    state["uptime"] = engine.uptime
    return state

def _guard():
    return engine.running

def _broadcast_engine_sync():
    
    try:
        eel.js_on_engine_sync({
            "running": engine.running,
            "uptime": engine.uptime,
            "mode": config.automation.get("mode", "idle"),
        })()
    except Exception:
        pass

def _broadcast_settings_sync():
    
    try:
        eel.js_on_settings_sync(dict(config.settings))()
    except Exception:
        pass

@eel.expose
def get_state():
    return _state_with_status()

@eel.expose
def get_status():
    engine.time.flush()
    return {
        "running": engine.running,
        "uptime": engine.uptime,
        "biomeCounts": dict(config.biome_counts),
        "unknownBiomes": dict(config.unknown_biomes),
        "merchantCounts": dict(config.merchant_counts),
        "moduleCounts": dict(config.module_counts),
        "edenStats": dict(config.eden_stats),
        "accountStates": engine.account_runtime(),
        "fishing": engine.automation.fishing.status(),
        "timeTracking": engine.time.live(),
    }

@eel.expose
def get_engine_signal():
    return {
        "running": engine.running,
        "uptime": engine.uptime,
        "module": engine.current_module(),
        "status": status_events.snapshot(),
    }

@eel.expose
def get_time_tracking():
    return engine.time.live()

@eel.expose
def reset_time_tracking():
    if _guard():
        return {"ok": False, "error": "running"}
    config.reset_time_tracking()
    return {"ok": True, "timeTracking": engine.time.live()}

@eel.expose
def add_account(name, link=""):
    if _guard():
        return _state_with_status()
    avatar = MacroEngine.get_roblox_avatar(name)
    config.add_account(name, link, avatar)
    return _state_with_status()

@eel.expose
def update_account(acc_id, name=None, link=None):
    if _guard():
        return _state_with_status()
    avatar = None
    existing = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if existing and name and name.strip() != existing.get("name"):
        avatar = MacroEngine.get_roblox_avatar(name)
    config.update_account(acc_id, name=name, link=link, avatar=avatar)
    return _state_with_status()

@eel.expose
def delete_account(acc_id):
    if _guard():
        return _state_with_status()
    config.delete_account(acc_id)
    return _state_with_status()

@eel.expose
def move_account(acc_id, direction):
    if _guard():
        return _state_with_status()
    config.move_account(acc_id, direction)
    return _state_with_status()

@eel.expose
def set_account_enabled(acc_id, enabled):
    if _guard():
        return _state_with_status()
    config.set_account_enabled(acc_id, bool(enabled))
    return _state_with_status()


def _is_point(v):
    return isinstance(v, (list, tuple)) and len(v) == 2

def _is_region(v):
    return isinstance(v, (list, tuple)) and len(v) == 4

def _inventory_calib_ready():
    px = config.automation.get("pixels", {}) or {}
    return all(_is_point(px.get(k)) for k in _auto_presets.slot_keys())

def _merchant_calib_ready():
    general = (((config.automation.get("merchants", {}) or {}).get("calib", {}) or {})
               .get("general", {}) or {})
    return (_is_point((general.get("pixels", {}) or {}).get("dialogue_skip"))
            and _is_region((general.get("regions", {}) or {}).get("merchant_name")))



def _merchant_autobuy_calib_ready():
    
    import core.merchants_data as _md
    calib = ((config.automation.get("merchants", {}) or {}).get("calib", {}) or {})

    def _points_ok(group):
        px = ((calib.get(group, {}) or {}).get("pixels", {}) or {})
        return all(_is_point(px.get(k)) for k in _md.calib_point_keys(group))

    def _regions_ok(group):
        rg = ((calib.get(group, {}) or {}).get("regions", {}) or {})
        keys = (_md.required_shop_region_keys() if group == "shop"
                else _md.calib_region_keys(group))
        return all(_is_region(rg.get(k)) for k in keys)

    return (_points_ok("shop") and _regions_ok("shop")
            and _points_ok("mari") and _points_ok("jester"))

FISHING_REQUIRED_SLOTS = ("cast_point", "bite_indicator", "bar_sample", "zone_left",
                          "zone_right", "reel_click", "claim_button")

def _fishing_calib_ready():
    px = (config.automation.get("fishing", {}) or {}).get("pixels", {}) or {}
    return all(_is_point(px.get(k)) for k in FISHING_REQUIRED_SLOTS)

def _autopop_calib_ready():
    region = (config.automation.get("autopop", {}) or {}).get("amountRegion")
    return _inventory_calib_ready() and _is_region(region)

@eel.expose
def set_account_module(acc_id, task, enabled):
    if _guard():
        return _state_with_status()
    if enabled:
        if task in ("strangeController", "biomeRandomizer") and not _inventory_calib_ready():
            return _state_with_status()
        if task == "merchantTeleporter" and not (
            ocr.available() and _inventory_calib_ready() and _merchant_calib_ready()
        ):
            return _state_with_status()
        if task == "fishing" and not _fishing_calib_ready():
            return _state_with_status()
    config.set_account_module(acc_id, task, enabled)
    return _state_with_status()

def _apply_token_refresh(acc_id, refreshed):
    
    if refreshed:
        try:
            config.set_account_token(acc_id, refreshed)
            print(f"[Auth] Account {acc_id}: captured a rotated Roblox cookie.")
        except Exception as e:
            print(f"[Auth] Could not store rotated cookie for {acc_id}: {e}")

@eel.expose
def set_account_token(acc_id, token):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    config.set_account_token(acc_id, token)
    info = roblox_auth.validate_token(config.account_token(acc_id))
    _apply_token_refresh(acc_id, info.get("refreshed"))
    if info.get("ok") or info.get("refreshed"):
        config.set_account_token_status(acc_id, info.get("name", ""), True)
        result = {"ok": True, "user": info.get("name", ""),
                  "displayName": info.get("displayName", "")}
    elif info.get("definitive"):
        config.set_account_token_status(acc_id, "", False)
        result = {"ok": False, "error": info.get("error", "invalid")}
    else:
        config.set_account_token_status(acc_id, "", True)
        result = {"ok": True, "user": "", "displayName": "", "unverified": True,
                  "error": info.get("error")}
    result["state"] = _state_with_status()
    return result

@eel.expose
def start_browser_login(acc_id):
    
    if _guard():
        return {"ok": False, "error": "running"}
    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}

    def _done(token, error):
        ok = False
        payload = error or "failed"
        if token:
            info = roblox_auth.validate_token(token)
            store_token = (info.get("refreshed") or token)
            if info.get("ok") or info.get("refreshed"):
                tname = (info.get("name") or "").strip()
                dname = (info.get("displayName") or "").strip()
                want = (acc.get("name") or "").strip()
                if want and tname and want.lower() not in (tname.lower(), dname.lower()):
                    payload = f"wrong_account:{tname}"
                else:
                    config.set_account_token(acc_id, store_token)
                    config.set_account_token_status(acc_id, tname, True)
                    ok, payload = True, tname
            elif info.get("definitive"):
                payload = info.get("error", "invalid")
            else:
                config.set_account_token(acc_id, token)
                config.set_account_token_status(acc_id, (acc.get("name") or "").strip(), True)
                ok, payload = True, (acc.get("name") or "").strip()
        try:
            eel.onBrowserLoginResult(acc_id, ok, payload)()
        except Exception:
            pass

    return browser_login.start(_done)

@eel.expose
def cancel_browser_login():
    browser_login.cancel()
    return {"ok": True}

@eel.expose
def clear_account_token(acc_id):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    config.clear_account_token(acc_id)
    return {"ok": True, "state": _state_with_status()}

@eel.expose
def revalidate_account_token(acc_id):
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token", "state": _state_with_status()}
    info = roblox_auth.validate_token(token)
    _apply_token_refresh(acc_id, info.get("refreshed"))
    if info.get("ok") or info.get("refreshed"):
        config.set_account_token_status(acc_id, info.get("name", ""), True)
        return {"ok": True, "user": info.get("name", ""), "state": _state_with_status()}
    if info.get("definitive"):
        config.set_account_token_status(acc_id, "", False)
        return {"ok": False, "error": info.get("error"), "state": _state_with_status()}
    return {"ok": False, "transient": True, "error": info.get("error"),
            "state": _state_with_status()}

@eel.expose
def get_performance():
    snap = perfmon.snapshot(config.enabled_accounts())
    try:
        snap["throttle"] = throttler.status()
    except Exception as e:
        print(f"[Throttle] status failed: {e}")
    return snap

@eel.expose
def get_throttle_state():
    return throttler.status()

@eel.expose
def trim_system_ram():
    return perfmon.trim_system_ram()

@eel.expose
def resolve_link_info(acc_id, link):

    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token"}
    import requests as _req
    place_info = roblox_auth.parse_private_link(token, link)
    if not place_info:
        return {"ok": False, "error": "invalid_link"}
    place_id = place_info.get("placeId")
    if not place_id:
        return {"ok": False, "error": "no_place_id"}
    try:

        r = _req.get(
            f"https://apis.roblox.com/universes/v1/places/{place_id}/universe",
            timeout=10)
        universe_id = r.json().get("universeId") if r.ok else None
        universe_name = ""
        owner_name = ""
        owner_type = ""
        thumb_url = ""
        if universe_id:

            r2 = _req.get(
                f"https://games.roblox.com/v1/games?universeIds={universe_id}",
                timeout=10)
            if r2.ok:
                data = r2.json().get("data", [])
                if data:
                    g = data[0]
                    universe_name = g.get("name", "")
                    creator = g.get("creator", {})
                    owner_name = creator.get("name", "")
                    owner_type = creator.get("type", "")

            r3 = _req.get(
                f"https://thumbnails.roblox.com/v1/games/icons?universeIds={universe_id}"
                f"&returnPolicy=PlaceHolder&size=128x128&format=Png&isCircular=false",
                timeout=10)
            if r3.ok:
                tdata = r3.json().get("data", [])
                if tdata:
                    thumb_url = tdata[0].get("imageUrl", "")
        return {
            "ok": True,
            "placeId": place_id,
            "universeId": universe_id,
            "universeName": universe_name,
            "ownerName": owner_name,
            "ownerType": owner_type,
            "thumbUrl": thumb_url,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@eel.expose
def teleport_in_bound_window(acc_id, link):

    from core import win_windows
    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token"}

    place_info = roblox_auth.parse_private_link(token, link)
    if not place_info:
        return {"ok": False, "error": "invalid_link"}

    resolved = win_windows.resolve_accounts([acc])
    info = resolved.get(acc_id, {})
    hwnd = info.get("hwnd")
    pid  = info.get("pid")
    in_place = bool(hwnd and pid and sys.platform == "win32")

    if in_place:
        try:
            win_windows.focus_hwnd(hwnd)
        except Exception:
            pass
        if roblox_auth.teleport_in_place(place_info):
            acc["launchTime"] = time.time()
            return {"ok": True, "method": "in_place", "rebound": True}
        return {"ok": False, "error": "deeplink_failed"}

    tmp = dict(acc)
    tmp["link"]  = link
    tmp["token"] = token
    res = roblox_auth.launch_account(tmp, mode="private")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "launch_failed")}
    acc["launchTime"] = time.time()
    return {"ok": True, "method": "new_window", "rebound": False}

@eel.expose
def launch_link_as_account(acc_id, link):

    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token"}

    tmp = dict(acc)
    tmp["link"] = link
    tmp["token"] = token
    res = roblox_auth.launch_account(tmp, mode="private")
    if res.get("ok"):
        acc["launchTime"] = time.time()
    return res

@eel.expose
def launch_account(acc_id, mode="home"):
    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token"}
    tmp = dict(acc)
    tmp["token"] = token
    res = roblox_auth.launch_account(tmp, mode=mode)
    _apply_token_refresh(acc_id, res.pop("refreshed", ""))
    if res.get("ok"):
        acc["launchTime"] = time.time()
    return res

@eel.expose
def get_account_windows():
    
    from core import win_windows
    try:
        resolved = win_windows.resolve_accounts(config.enabled_accounts())
    except Exception as e:
        print(f"[Windows] Idle resolve failed: {e}")
        resolved = {}
    out = []
    for a in config.accounts:
        aid = a.get("id")
        if not a.get("enabled", True):
            out.append({"id": aid, "online": False, "currentBiome": None,
                        "window": None, "hwndKnown": False})
            continue
        info = resolved.get(aid, {})
        out.append({
            "id": aid,
            "online": bool(info.get("online")),
            "currentBiome": None,
            "window": info.get("label"),
            "hwndKnown": info.get("hwnd") is not None,
        })
    return out

@eel.expose
def launch_all_accounts(mode="home"):
    results = []
    launched = 0
    for acc in config.enabled_accounts():
        token = config.account_token(acc.get("id"))
        if not token:
            results.append({"id": acc.get("id"), "name": acc.get("name"),
                            "ok": False, "error": "no_token"})
            continue
        tmp = dict(acc)
        tmp["token"] = token
        res = roblox_auth.launch_account(tmp, mode=mode)
        _apply_token_refresh(acc.get("id"), res.pop("refreshed", ""))
        res["id"] = acc.get("id")
        res["name"] = acc.get("name")
        results.append(res)
        if res.get("ok"):
            acc["launchTime"] = time.time()
            launched += 1
            time.sleep(2.5)
    return {"ok": launched > 0, "launched": launched, "results": results}

_bind_cancel = threading.Event()

@eel.expose
def start_bind_window(acc_id):
    from core import win_windows
    acc = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if not acc:
        return {"ok": False, "error": "no_account"}
    _bind_cancel.clear()

    def _run():
        print(f"[Bind] Waiting for click to bind '{acc.get('name')}'…")
        hwnd, pid = win_windows.hwnd_from_click(timeout=30.0,
                                                cancel_flag=lambda: _bind_cancel.is_set())
        if hwnd and pid:
            win_windows.set_manual_bind(acc_id, hwnd, pid)
            print(f"[Bind] '{acc.get('name')}' manually bound → hwnd {hwnd} pid {pid}")
            ok, reason = True, f"Window {hwnd}"
        else:
            ok = False
            reason = "cancelled" if _bind_cancel.is_set() else "timeout_or_not_roblox"
            print(f"[Bind] '{acc.get('name')}' bind failed: {reason}")
        try:
            eel.onBindResult(acc_id, ok, reason)()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True}

@eel.expose
def cancel_bind_window():
    _bind_cancel.set()
    return {"ok": True}

@eel.expose
def clear_bind_window(acc_id):
    from core import win_windows
    win_windows.clear_manual_bind(acc_id)
    print(f"[Bind] Manual bind cleared for acc {acc_id}")
    return {"ok": True}

@eel.expose
def set_fishing_account(acc_id):
    if _guard():
        return _state_with_status()
    if acc_id is not None and not _fishing_calib_ready():
        return _state_with_status()
    config.set_fishing_account(acc_id)
    return _state_with_status()

@eel.expose
def set_fishing_schedule(schedule):
    if _guard():
        return _state_with_status()
    config.set_fishing_schedule(schedule)
    return _state_with_status()


@eel.expose
def wipe_config():
    
    if _guard():
        return {"ok": False, "error": "running"}
    config.reset_to_defaults()
    return {"ok": True}


@eel.expose
def set_eden_account(acc_id):
    if _guard():
        return _state_with_status()
    config.set_eden_account(acc_id)
    return _state_with_status()

@eel.expose
def set_eden_setting(key, value):
    if _guard():
        return _state_with_status()
    config.set_eden_setting(key, value)
    return _state_with_status()

@eel.expose
def add_webhook(name, url):
    if _guard():
        return _state_with_status()
    config.add_webhook(name, url)
    return _state_with_status()

@eel.expose
def update_webhook(wh_id, name=None, url=None):
    if _guard():
        return _state_with_status()
    config.update_webhook(wh_id, name=name, url=url)
    return _state_with_status()

@eel.expose
def delete_webhook(wh_id):
    if _guard():
        return _state_with_status()
    config.delete_webhook(wh_id)
    return _state_with_status()

@eel.expose
def set_webhook_active(wh_id, active):
    if _guard():
        return _state_with_status()
    config.set_webhook_active(wh_id, active)
    return _state_with_status()

@eel.expose
def set_routing(wh_id, acc_id, enabled):
    if _guard():
        return _state_with_status()
    config.set_routing(wh_id, acc_id, enabled)
    return _state_with_status()

@eel.expose
def set_biome_logging(value):
    if _guard():
        return _state_with_status()
    enabled = bool(value)
    if enabled and not engine.logging_requirements_met():
        return _state_with_status()
    config.set_setting("biomeLogging", enabled)
    return _state_with_status()

@eel.expose
def set_biome_ping(biome_key, ptype, pid):
    
    config.set_biome_ping(biome_key, ptype, pid)
    return _state_with_status()

@eel.expose
def set_setting(key, value):
    if key == "antiAfkEnabled" and engine.running:
        return _state_with_status()
    config.set_setting(key, value)
    if key == "hotkey":
        _register_hotkey(str(value))
    if key == "modeHotkey":
        _register_mode_hotkey(str(value))
    if key in ("ramTrimEnabled", "ramTrimInterval"):
        ram_trimmer.sync()
    if key in ("throttleEnabled", "throttleMethod", "throttleCycleMs", "throttleQuota",
               "throttleFocusAware", "throttleOnlyWhenRunning", "throttleScope",
               "throttleBreathe", "throttleRamCap",
               "throttleRamCapMb", "throttleAccounts"):
        throttler.sync()
    if key in ("antiAfkStandalone", "antiAfkEnabled", "antiAfkInterval", "antiAfkAction"):
        engine.refresh_anti_afk()
    _broadcast_settings_sync()
    return _state_with_status()

@eel.expose
def set_automation_mode(mode):
    engine.set_automation_mode(mode)
    _broadcast_engine_sync()
    return _state_with_status()

@eel.expose
def set_automation_task(task, enabled):
    if _guard():
        return _state_with_status()
    config.set_automation_task(task, enabled)
    return _state_with_status()

@eel.expose
def set_automation_search(task, term):
    if _guard():
        return _state_with_status()
    config.set_search_term(task, term)
    return _state_with_status()

@eel.expose
def set_automation_amount(value):
    if _guard():
        return _state_with_status()
    config.set_amount(value)
    return _state_with_status()

@eel.expose
def get_automation_presets():
    return {"presets": presets.preset_names(), "slots": presets.PIXEL_SLOTS}

@eel.expose
def load_automation_preset(name):
    if _guard():
        return _state_with_status()
    config.load_preset_pixels(name)
    return _state_with_status()

@eel.expose
def capture_item_region():

    if _guard():
        return {"ok": False, "error": "tracking_active"}
    p1 = engine.automation._capture_click(timeout=30.0)
    if not p1:
        return {"ok": False, "error": "timeout"}
    p2 = engine.automation._capture_click(timeout=30.0)
    if not p2:
        return {"ok": False, "error": "timeout"}
    config.set_first_item_region(p1, p2)
    x = min(p1[0], p2[0]); y = min(p1[1], p2[1])
    w = abs(p2[0]-p1[0]); h = abs(p2[1]-p1[1])
    print(f"[Calibration] Item region set → ({x},{y}) {w}×{h}px, click centre ({x+w//2},{y+h//2})")
    return {"ok": True, "region": [x, y, w, h]}

@eel.expose
def clear_item_region():
    if _guard():
        return _state_with_status()
    config.clear_first_item_region()
    return _state_with_status()

@eel.expose
def capture_pixel(slot):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    return engine.automation.capture(slot)

@eel.expose
def clear_pixel(slot):
    if _guard():
        return _state_with_status()
    config.set_pixel(slot, None)
    return _state_with_status()

@eel.expose
def get_fishing_presets():
    return {
        "presets": fishing_presets.preset_names(),
        "routes": fishing_presets.route_names(),
        "slots": fishing_presets.PIXEL_SLOTS,
    }

@eel.expose
def set_fishing_enabled(value):
    if _guard():
        return _state_with_status()
    config.set_fishing("enabled", bool(value))
    return _state_with_status()

@eel.expose
def set_fishing_account_setting(acc_id, key, value):
    if _guard():
        return _state_with_status()
    config.set_fishing_account_setting(acc_id, key, value)
    return _state_with_status()

@eel.expose
def set_fishing_webhook(enabled):

    config.set_fishing("webhookEnabled", bool(enabled))
    return _state_with_status()

@eel.expose
def load_fishing_preset(name):
    if _guard():
        return _state_with_status()
    config.load_fishing_preset(name)
    return _state_with_status()


@eel.expose
def capture_fishing_pixel(slot):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    return engine.automation.fishing.capture(slot)

@eel.expose
def clear_fishing_pixel(slot):
    if _guard():
        return _state_with_status()
    config.set_fishing_pixel(slot, None)
    return _state_with_status()

@eel.expose
def capture_fishing_region(name):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    if name not in fishing_presets.region_keys():
        return {"ok": False, "error": "bad_region"}
    p1 = engine.automation._capture_click(timeout=30.0)
    if not p1:
        return {"ok": False, "error": "timeout"}
    p2 = engine.automation._capture_click(timeout=30.0)
    if not p2:
        return {"ok": False, "error": "timeout"}
    config.set_fishing_region(name, p1, p2)
    x = min(p1[0], p2[0]); y = min(p1[1], p2[1])
    w = abs(p2[0]-p1[0]); h = abs(p2[1]-p1[1])
    print(f"[Calibration] Fishing region '{name}' set → ({x},{y}) {w}×{h}px")
    return {"ok": True, "region": [x, y, w, h]}

@eel.expose
def clear_fishing_region(name):
    if _guard():
        return _state_with_status()
    config.clear_fishing_region(name)
    return _state_with_status()

@eel.expose
def get_ocr_status():
    from core import tesseract_install
    ocr.reset_cache()
    st = ocr.status()
    st["installing"] = tesseract_install.is_installing()
    st["installed"] = tesseract_install.is_installed()
    if not st.get("available") and st.get("installed"):
        st["binaryPresent"] = True
    return st

@eel.expose
def install_tesseract():
    
    from core import tesseract_install
    if ocr.available():
        return {"ok": False, "error": "already_installed"}
    if tesseract_install.is_installing():
        return {"ok": False, "error": "already_installing"}

    def _progress(payload):
        try:
            eel.onTesseractProgress(payload)()
        except Exception:
            pass

    def _run():
        res = tesseract_install.install(progress=_progress)
        ocr.reset_cache()
        res["available"] = ocr.available()
        try:
            eel.onTesseractDone(res)()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "started": True}

@eel.expose
def set_ocr_failsafe(task, enabled):
    if _guard():
        return _state_with_status()
    if enabled and task != "noBite" and not ocr.available():
        return _state_with_status()
    config.set_ocr_failsafe(task, bool(enabled))
    return _state_with_status()

@eel.expose
def set_notification(key, enabled):

    config.set_notification(key, bool(enabled))
    return _state_with_status()

@eel.expose
def set_merchant_interval(value):
    if _guard():
        return _state_with_status()
    config.set_merchant_interval(value)
    return _state_with_status()

@eel.expose
def capture_merchant_pixel(group, slot):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    import core.merchants_data as _md
    if slot not in _md.calib_point_keys(group):
        return {"ok": False, "error": "bad_slot"}
    pos = engine.automation._capture_click(timeout=30.0)
    if not pos:
        return {"ok": False, "error": "timeout"}
    config.set_merchant_pixel(group, slot, [pos[0], pos[1]])
    print(f"[Calibration] Merchant '{group}/{slot}' → {pos[0]}, {pos[1]}")
    return {"ok": True, "group": group, "slot": slot, "x": pos[0], "y": pos[1]}

@eel.expose
def clear_merchant_pixel(group, slot):
    if _guard():
        return _state_with_status()
    config.clear_merchant_pixel(group, slot)
    return _state_with_status()

@eel.expose
def capture_merchant_region(group, name):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    import core.merchants_data as _md
    if name not in _md.calib_region_keys(group):
        return {"ok": False, "error": "bad_region"}
    p1 = engine.automation._capture_click(timeout=30.0)
    if not p1:
        return {"ok": False, "error": "timeout"}
    p2 = engine.automation._capture_click(timeout=30.0)
    if not p2:
        return {"ok": False, "error": "timeout"}
    config.set_merchant_region(group, name, p1, p2)
    x = min(p1[0], p2[0]); y = min(p1[1], p2[1])
    w = abs(p2[0]-p1[0]); h = abs(p2[1]-p1[1])
    print(f"[Calibration] Merchant region '{group}/{name}' set → ({x},{y}) {w}×{h}px")
    return {"ok": True, "group": group, "region": [x, y, w, h]}

@eel.expose
def clear_merchant_region(group, name):
    if _guard():
        return _state_with_status()
    config.clear_merchant_region(group, name)
    return _state_with_status()

@eel.expose
def capture_extra_pixel(group, slot):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    import core.extra_calibrations as _ec
    if slot not in _ec.point_keys(group):
        return {"ok": False, "error": "bad_slot"}
    pos = engine.automation._capture_click(timeout=30.0)
    if not pos:
        return {"ok": False, "error": "timeout"}
    config.set_extra_pixel(group, slot, [pos[0], pos[1]])
    print(f"[Calibration] Extra '{group}/{slot}' → {pos[0]}, {pos[1]}")
    return {"ok": True, "group": group, "slot": slot, "x": pos[0], "y": pos[1]}

@eel.expose
def clear_extra_pixel(group, slot):
    if _guard():
        return _state_with_status()
    config.clear_extra_pixel(group, slot)
    return _state_with_status()

@eel.expose
def capture_extra_region(group, name):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    import core.extra_calibrations as _ec
    if name not in _ec.region_keys(group):
        return {"ok": False, "error": "bad_region"}
    p1 = engine.automation._capture_click(timeout=30.0)
    if not p1:
        return {"ok": False, "error": "timeout"}
    p2 = engine.automation._capture_click(timeout=30.0)
    if not p2:
        return {"ok": False, "error": "timeout"}
    config.set_extra_region(group, name, p1, p2)
    x = min(p1[0], p2[0]); y = min(p1[1], p2[1])
    w = abs(p2[0]-p1[0]); h = abs(p2[1]-p1[1])
    print(f"[Calibration] Extra region '{group}/{name}' set → ({x},{y}) {w}×{h}px")
    return {"ok": True, "group": group, "region": [x, y, w, h]}

@eel.expose
def clear_extra_region(group, name):
    if _guard():
        return _state_with_status()
    config.clear_extra_region(group, name)
    return _state_with_status()

@eel.expose
def set_merchant_autobuy(acc_id, mid, enabled):
    if _guard():
        return _state_with_status()
    if enabled:
        if not (ocr.available() and _merchant_autobuy_calib_ready()):
            return _state_with_status()
        items = config.merchant_autobuy(acc_id, mid).get("items", [])
        if not any(i.get("all") or int(i.get("amount", 0) or 0) > 0 for i in items):
            return _state_with_status()
    config.set_merchant_autobuy_enabled(acc_id, mid, bool(enabled))
    return _state_with_status()

@eel.expose
def set_merchant_autobuy_items(acc_id, mid, items):
    if _guard():
        return _state_with_status()
    config.set_merchant_autobuy_items(acc_id, mid, items)
    return _state_with_status()

@eel.expose
def reset_merchant_buy_log():
    config.reset_merchant_buy_log()
    return _state_with_status()

@eel.expose
def get_merchant_presets():
    import core.merchant_presets as _mp
    return {"presets": _mp.preset_names()}

@eel.expose
def load_merchant_preset(name):
    if _guard():
        return _state_with_status()
    config.load_merchant_preset(name)
    return _state_with_status()

@eel.expose
def get_extra_presets():
    import core.extra_presets as _ep
    return {"presets": _ep.preset_names()}

@eel.expose
def load_extra_preset(name):
    if _guard():
        return _state_with_status()
    config.load_extra_preset(name)
    return _state_with_status()

@eel.expose
def get_autopop_biomes():
    import core.autopop as _ap
    unknown = sorted((config.unknown_biomes or {}).keys())
    return {"biomes": _ap.biome_keys(),
            "unknown": ["unknown:" + n for n in unknown]}

@eel.expose
def set_autopop_option(key, enabled):
    if enabled and key == "ocrFailsafe" and not ocr.available():
        return _state_with_status()
    config.set_autopop_option(key, bool(enabled))
    return _state_with_status()

@eel.expose
def set_autopop_account(acc_id, enabled):
    if _guard():
        return _state_with_status()
    if enabled and not _autopop_calib_ready():
        return _state_with_status()
    config.set_autopop_account(acc_id, bool(enabled))
    return _state_with_status()

@eel.expose
def set_autopop_account_biome_enabled(acc_id, biome_key, enabled):
    if _guard():
        return _state_with_status()
    config.set_autopop_account_biome_enabled(acc_id, biome_key, bool(enabled))
    return _state_with_status()

@eel.expose
def set_autopop_account_items(acc_id, biome_key, items):
    if _guard():
        return _state_with_status()
    config.set_autopop_account_items(acc_id, biome_key, items)
    return _state_with_status()

@eel.expose
def capture_autopop_amount_region():
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    p1 = engine.automation._capture_click(timeout=30.0)
    if not p1:
        return {"ok": False, "error": "timeout"}
    p2 = engine.automation._capture_click(timeout=30.0)
    if not p2:
        return {"ok": False, "error": "timeout"}
    config.set_autopop_amount_region(p1, p2)
    x = min(p1[0], p2[0]); y = min(p1[1], p2[1])
    w = abs(p2[0]-p1[0]); h = abs(p2[1]-p1[1])
    print(f"[Calibration] Auto Pop amount region set -> ({x},{y}) {w}x{h}px")
    return {"ok": True, "region": [x, y, w, h]}

@eel.expose
def clear_autopop_amount_region():
    if _guard():
        return _state_with_status()
    config.clear_autopop_amount_region()
    return _state_with_status()

@eel.expose
def save_autopop_preset(acc_id, name):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    ok = config.save_autopop_preset(acc_id, name)
    return {"ok": bool(ok), "state": _state_with_status()}

@eel.expose
def load_autopop_preset(acc_id, name):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    ok = config.load_autopop_preset(acc_id, name)
    return {"ok": bool(ok), "state": _state_with_status()}

@eel.expose
def delete_autopop_preset(name):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    ok = config.delete_autopop_preset(name)
    return {"ok": bool(ok), "state": _state_with_status()}

@eel.expose
def export_autopop_preset(name, acc_id=None):
    import json as _json
    data = config.export_autopop_preset(name, acc_id=acc_id)
    return {"ok": True, "name": data.get("name", name), "json": _json.dumps(data)}

@eel.expose
def import_autopop_preset(name, payload):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    res = config.import_autopop_preset(name, payload)
    res["state"] = _state_with_status()
    return res

@eel.expose
def start_macro():
    result = engine.start()
    _broadcast_engine_sync()
    return result

@eel.expose
def stop_macro():
    result = engine.stop()
    _broadcast_engine_sync()
    return result

@eel.expose
def get_roblox_avatar(username):
    return MacroEngine.get_roblox_avatar(username)

@eel.expose
def check_update():
    current = config.data.get("version", "?")
    return updater.check_for_update(current)

@eel.expose
def open_url(url):
    if url and isinstance(url, str) and url.startswith(("http://", "https://")):
        try:
            webbrowser.open(url)
            return True
        except Exception as e:
            print(f"[Update] Could not open url: {e}")
    return False

@eel.expose
def window_minimize():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.ShowWindow(hwnd, 6)
        return True
    except Exception:
        return False

@eel.expose
def window_maximize():
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        is_max = ctypes.windll.user32.IsZoomed(hwnd)
        ctypes.windll.user32.ShowWindow(hwnd, 9 if not is_max else 1)
        return not bool(is_max)
    except Exception:
        return False

@eel.expose
def window_close():
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return True
    except Exception:
        return False

@eel.expose
def close_app_window():
    
    try:
        return {"ok": bool(eel.close_app())}
    except Exception:
        return {"ok": False}

@eel.expose
def get_releases():
    current = config.data.get("version", "?")
    return updater.get_all_releases(current)

@eel.expose
def download_and_install_update(url, name=""):
    
    from core import self_update
    if self_update.is_busy():
        return {"ok": False, "error": "already_running"}

    def _progress(payload):
        try:
            eel.onUpdateProgress(payload)()
        except Exception:
            pass

    def _run():
        res = self_update.download_and_launch(url, name or None, progress=_progress)
        try:
            eel.onUpdateDone(res)()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "started": True}

_MERCHANT_GROUP_COLORS = {
    "general": "#f59e0b",
    "shop":    "#fb923c",
    "mari":    "#a855f7",
    "jester":  "#22d3ee",
    "rin":     "#34d399",
}

def _collect_merchant_points():
    import core.merchants_data as _md
    auto = config.automation
    calib = ((auto.get("merchants", {}) or {}).get("calib", {}) or {})
    points = []
    for group in _md.calib_groups():
        gkey = group["key"]
        color = _MERCHANT_GROUP_COLORS.get(gkey, "#f59e0b")
        gpix = (calib.get(gkey, {}) or {}).get("pixels", {}) or {}
        for slot, label in group.get("points", []):
            pos = gpix.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append({"x": pos[0], "y": pos[1],
                               "label": f"{group['label']}: {label}", "color": color})
    return points

def _collect_merchant_regions():
    import core.merchants_data as _md
    auto = config.automation
    calib = ((auto.get("merchants", {}) or {}).get("calib", {}) or {})
    regions = []
    for group in _md.calib_groups():
        gkey = group["key"]
        color = _MERCHANT_GROUP_COLORS.get(gkey, "#f59e0b")
        grgn = (calib.get(gkey, {}) or {}).get("regions", {}) or {}
        for name, label in group.get("regions", []):
            box = grgn.get(name)
            if isinstance(box, (list, tuple)) and len(box) == 4:
                regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                "label": f"{group['label']}: {label}", "color": color})
    return regions

def _collect_extra_points():
    import core.extra_calibrations as _ec
    calib = config.automation.get("calib", {}) or {}
    points = []
    for group in _ec.groups():
        gkey = group["key"]
        color = group.get("color", "#e2e8f0")
        gpix = (calib.get(gkey, {}) or {}).get("pixels", {}) or {}
        for slot, label in group.get("points", []):
            pos = gpix.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append({"x": pos[0], "y": pos[1],
                               "label": f"{group['label']}: {label}", "color": color})
        for sg in group.get("subgroups", []):
            for slot, label in sg.get("points", []):
                pos = gpix.get(slot)
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    points.append({"x": pos[0], "y": pos[1],
                                   "label": f"{group['label']}: {sg['label']}: {label}",
                                   "color": color})
    return points

def _collect_extra_regions():
    import core.extra_calibrations as _ec
    calib = config.automation.get("calib", {}) or {}
    regions = []
    for group in _ec.groups():
        gkey = group["key"]
        color = group.get("color", "#e2e8f0")
        grgn = (calib.get(gkey, {}) or {}).get("regions", {}) or {}
        for name, label in group.get("regions", []):
            box = grgn.get(name)
            if isinstance(box, (list, tuple)) and len(box) == 4:
                regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                "label": f"{group['label']}: {label}", "color": color})
        for sg in group.get("subgroups", []):
            for name, label in sg.get("regions", []):
                box = grgn.get(name)
                if isinstance(box, (list, tuple)) and len(box) == 4:
                    regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                    "label": f"{group['label']}: {sg['label']}: {label}",
                                    "color": color})
    return regions

def _collect_points(scope):
    auto = config.automation
    points = []
    if scope in ("automation", "all"):
        pixels = auto.get("pixels", {}) or {}
        for slot, label in _auto_presets.PIXEL_SLOTS:
            pos = pixels.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append({"x": pos[0], "y": pos[1], "label": label, "color": "#4f6ef7"})
    if scope in ("merchants", "all"):
        points.extend(_collect_merchant_points())
    if scope in ("fishing", "all"):
        fpixels = (auto.get("fishing", {}) or {}).get("pixels", {}) or {}
        for slot, label in _fish_presets.PIXEL_SLOTS:
            pos = fpixels.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append({"x": pos[0], "y": pos[1], "label": label, "color": "#22d3ee"})
    if scope in ("chat", "aura_storage", "fischl", "crafting", "loading_screen", "ps_check", "all"):
        import core.extra_calibrations as _ec
        all_pts = _collect_extra_points()
        all_rgns_extra = _collect_extra_regions()
        if scope == "all":
            points.extend(all_pts)
        else:
            g = _ec.group(scope)
            if g:
                calib = config.automation.get("calib", {}) or {}
                gpix = (calib.get(scope, {}) or {}).get("pixels", {}) or {}
                color = g.get("color", "#e2e8f0")
                for slot, label in g.get("points", []):
                    pos = gpix.get(slot)
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        points.append({"x": pos[0], "y": pos[1], "label": label, "color": color})
                for sg in g.get("subgroups", []):
                    for slot, label in sg.get("points", []):
                        pos = gpix.get(slot)
                        if isinstance(pos, (list, tuple)) and len(pos) == 2:
                            points.append({"x": pos[0], "y": pos[1],
                                           "label": f"{sg['label']}: {label}", "color": color})
    return points

def _collect_regions(scope):
    auto = config.automation
    regions = []
    if scope in ("automation", "all"):
        item = auto.get("firstItemRegion")
        if isinstance(item, (list, tuple)) and len(item) == 4:
            regions.append({"x": item[0], "y": item[1], "w": item[2], "h": item[3],
                            "label": "First Item Region", "color": "#4f6ef7"})
    if scope in ("merchants", "all"):
        regions.extend(_collect_merchant_regions())
    if scope in ("fishing", "all"):
        fregions = (auto.get("fishing", {}) or {}).get("regions", {}) or {}
        for nm, box in fregions.items():
            if isinstance(box, (list, tuple)) and len(box) == 4:
                regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                "label": _fish_presets.region_label(nm), "color": "#22d3ee"})
    if scope in ("chat", "aura_storage", "fischl", "crafting", "loading_screen", "ps_check", "all"):
        import core.extra_calibrations as _ec
        if scope == "all":
            regions.extend(_collect_extra_regions())
        else:
            g = _ec.group(scope)
            if g:
                calib = config.automation.get("calib", {}) or {}
                grgn = (calib.get(scope, {}) or {}).get("regions", {}) or {}
                color = g.get("color", "#e2e8f0")
                for name, label in g.get("regions", []):
                    box = grgn.get(name)
                    if isinstance(box, (list, tuple)) and len(box) == 4:
                        regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                        "label": label, "color": color})
                for sg in g.get("subgroups", []):
                    for name, label in sg.get("regions", []):
                        box = grgn.get(name)
                        if isinstance(box, (list, tuple)) and len(box) == 4:
                            regions.append({"x": box[0], "y": box[1], "w": box[2], "h": box[3],
                                            "label": f"{sg['label']}: {label}", "color": color})
    return regions

@eel.expose
def show_calibration_points(scope="all", duration=4.0):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    _VALID_SCOPES = {"automation", "fishing", "merchants",
                     "chat", "aura_storage", "fischl", "crafting", "loading_screen", "ps_check", "all"}
    norm = scope if scope in _VALID_SCOPES else "all"
    points = _collect_points(norm)
    regions = _collect_regions(norm)
    if not points and not regions:
        return {"ok": False, "error": "no_points"}
    try:
        d = max(2.0, min(15.0, float(duration)))
    except (TypeError, ValueError):
        d = 4.0
    return overlay.show_points(points, d, regions=regions)



@eel.expose
def set_tutorial_seen(kind, version=""):
    if kind == "firstStart":
        config.set_setting("firstStartDone", True)
    elif kind == "update":
        config.set_setting("tutorialVersion", str(version or ""))
    return _state_with_status()

@eel.expose
def reset_tutorial():
    config.set_setting("firstStartDone", False)
    config.set_setting("tutorialVersion", "")
    return _state_with_status()

@eel.expose
def get_creator_info():
    info = creator.links()
    info["stats"] = creator.get_stats()
    return info

@eel.expose
def refresh_creator_stats():
    return creator.get_stats(force=True)


@eel.expose
def get_calibration_text(scope):
    region_keys, regions = [], {}
    if scope == "fishing":
        keys = fishing_presets.slot_keys()
        fish = config.automation.get("fishing", {}) or {}
        pixels = fish.get("pixels", {}) or {}
        regions = fish.get("regions", {}) or {}
        region_keys = fishing_presets.region_keys()
        label = "fishing"
    elif scope == "merchants":
        return _merchant_calibration_text()
    elif scope == "all":
        return _all_calibration_text()
    elif scope in ("chat", "aura_storage", "fischl", "crafting", "loading_screen", "ps_check"):
        return _extra_calibration_text(scope)
    else:
        keys = presets.slot_keys()
        pixels = config.automation.get("pixels", {}) or {}
        label = "inventory"
    lines = [f"# SolRich {label} calibration", '    "MY RESOLUTION (rename me)": {']
    for key in keys:
        value = pixels.get(key)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            lines.append(f'        "{key}": [{int(value[0])}, {int(value[1])}],')
        else:
            lines.append(f'        "{key}": None,')
    for name in region_keys:
        v = regions.get(name)
        if isinstance(v, (list, tuple)) and len(v) == 4:
            lines.append(f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],')
        else:
            lines.append(f'        "{name}": None,')
    lines.append("    },")
    return "\n".join(lines)

def _extra_calibration_text(scope):
    import core.extra_calibrations as _ec
    g = _ec.group(scope)
    if not g:
        return ""
    calib = config.automation.get("calib", {}) or {}
    gdata = calib.get(scope, {}) or {}
    gpix = gdata.get("pixels", {}) or {}
    grgn = gdata.get("regions", {}) or {}
    lines = [f'# SolRich {g["label"]} calibration', '    "MY RESOLUTION (rename me)": {']
    for slot, _lbl in g.get("points", []):
        v = gpix.get(slot)
        lines.append(f'        "{slot}": [{int(v[0])}, {int(v[1])}],' if isinstance(v, (list,tuple)) and len(v)==2 else f'        "{slot}": None,')
    for name, _lbl in g.get("regions", []):
        v = grgn.get(name)
        lines.append(f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],' if isinstance(v, (list,tuple)) and len(v)==4 else f'        "{name}": None,')
    for sg in g.get("subgroups", []):
        lines.append(f'        # {sg["label"]}')
        for slot, _lbl in sg.get("points", []):
            v = gpix.get(slot)
            lines.append(f'        "{slot}": [{int(v[0])}, {int(v[1])}],' if isinstance(v, (list,tuple)) and len(v)==2 else f'        "{slot}": None,')
        for name, _lbl in sg.get("regions", []):
            v = grgn.get(name)
            lines.append(f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],' if isinstance(v, (list,tuple)) and len(v)==4 else f'        "{name}": None,')
    lines.append("    },")
    return "\n".join(lines)

def _all_calibration_text():
    import core.extra_calibrations as _ec
    parts = []
    parts.append("# SolRich — All calibrations\n")
    parts.append("# == Inventory ==")
    parts.append(get_calibration_text("automation"))
    parts.append("\n# == Fishing ==")
    parts.append(get_calibration_text("fishing"))
    parts.append("\n# == Merchants ==")
    parts.append(_merchant_calibration_text())
    for g in _ec.groups():
        parts.append(f'\n# == {g["label"]} ==')
        parts.append(_extra_calibration_text(g["key"]))
    auto = config.automation
    def _fmt_region(v):
        if isinstance(v, (list, tuple)) and len(v) == 4:
            return f"[{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}]"
        return "None"
    fir = auto.get("firstItemRegion")
    amount = (auto.get("autopop", {}) or {}).get("amountRegion")
    parts.append("\n# == Regions ==")
    parts.append(f'    "first_item_region": {_fmt_region(fir)},')
    parts.append(f'    "autopop_amount_region": {_fmt_region(amount)},')
    return "\n".join(parts)

def _merchant_calibration_text():
    import core.merchants_data as _md
    calib = ((config.automation.get("merchants", {}) or {}).get("calib", {}) or {})
    lines = ["# SolRich merchant calibration"]
    for group in _md.calib_groups():
        gkey = group["key"]
        g = calib.get(gkey, {}) or {}
        gpix = g.get("pixels", {}) or {}
        grgn = g.get("regions", {}) or {}
        lines.append(f'    "{gkey}": {{  # {group["label"]}')
        for slot, _lbl in group.get("points", []):
            v = gpix.get(slot)
            if isinstance(v, (list, tuple)) and len(v) == 2:
                lines.append(f'        "{slot}": [{int(v[0])}, {int(v[1])}],')
            else:
                lines.append(f'        "{slot}": None,')
        for name, _lbl in group.get("regions", []):
            v = grgn.get(name)
            if isinstance(v, (list, tuple)) and len(v) == 4:
                lines.append(f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],')
            else:
                lines.append(f'        "{name}": None,')
        lines.append("    },")
    return "\n".join(lines)


@eel.expose
def tick_streak():
    return config.touch_streak()

@eel.expose
def reset_biome_counts():
    config.reset_biome_counts()
    return _state_with_status()

@eel.expose
def reset_eden_stats():
    config.reset_eden_stats()
    return _state_with_status()





def run():
    
    print(f"[Finnerich] Config folder: {config.dir}")

    saved_hotkey = config.settings.get("hotkey", "F5")
    _register_hotkey(saved_hotkey)
    saved_mode_hotkey = config.settings.get("modeHotkey", "none")
    _register_mode_hotkey(saved_mode_hotkey)

    ram_trimmer.start()

    throttler.start()

    engine.refresh_anti_afk()

    profile_dir = os.path.join(config.dir, "web_profile")


    browser_modes = ["chrome", "edge", "default"]

    for mode in browser_modes:
        try:
            print(f"[SolRich] Trying to run app in '{mode}' mode...")

            cmd_args = []
            if mode in ["chrome", "edge"]:
                cmd_args = [
                    f'--user-data-dir={profile_dir}',
                    '--no-first-run',
                    '--new-window',
                ]

            eel.start(
                "index.html",
                size=(1080, 720),
                mode=mode,
                cmdline_args=cmd_args,
                port=0,
            )

            break

        except (EnvironmentError, ValueError) as e:
            print(f"[SolRich] Mode '{mode}' failed. Trying next mode...")
            continue

        except (SystemExit, MemoryError, KeyboardInterrupt):
            engine.stop()
            break


if __name__ == "__main__":
    run()
