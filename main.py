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
from core import calibration_guides
from core import win_windows
from core import status_events
from core import activity_log
from core import account_timeline
from core import display_calibration
from core import monitor_dim
from core import windows_notifications
from core import support_bundle
from core import windows_search

from core import creator
from core import roblox_auth

from core import perf as perfmon
from core import ram_trim
from core import throttle as throttle_mod
from core import performance_benchmark as performance_benchmark_mod
from core import browser_login as browser_login_mod
from core import roblox_cleanup as roblox_cleanup_mod

from core import presets as _auto_presets
from core import fishing_presets as _fish_presets
from core import ocr
from core.secure_store import SecureStoreError
from core.anti_afk import focus_roblox


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
        print(
            "[SolRich] Started as administrator — relaunching without elevation "
            "so the window renders (admin isn't needed)."
        )
        ctypes.windll.shell32.ShellExecuteW(
            None, "open", "explorer.exe", f'"{exe}"', None, 1
        )
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        print(f"[SolRich] Could not de-elevate ({e}); continuing as administrator.")


_maybe_relaunch_deelevated()

eel.init(
    os.environ.get("SOLRICH_WEB") or os.environ.get("BIOMERICH_WEB", "web-react-dist")
)

config = ConfigManager()
try:
    from core import applog as _applog

    _applog.setup(config.dir)
except Exception:
    pass


def _refresh_missing_account_profiles():
    
    missing = [
        account for account in config.accounts
        if not account.get("robloxUserId") and account.get("name")
    ]
    if not missing:
        return
    profiles = MacroEngine.get_roblox_profiles(account.get("name") for account in missing)
    changed = False
    for account in missing:
        profile = profiles.get(str(account.get("name") or "").casefold())
        if not profile or not profile.get("id"):
            continue
        account["robloxUserId"] = profile["id"]
        account["robloxUsername"] = profile.get("name", "")
        changed = True
    if changed:
        config.save()


if "pytest" not in sys.modules:
    threading.Thread(
        target=_refresh_missing_account_profiles,
        name="roblox-profile-backfill",
        daemon=True,
    ).start()




try:
    _restored_windows = win_windows.resolve_accounts(config.accounts)
    if any(info.get("hwnd") for info in _restored_windows.values()):
        config.save()
except Exception as _restore_error:
    print(f"[Windows] Startup binding restore failed: {_restore_error}")

engine = MacroEngine(config)


def _show_blocked_rare_ping(payload):
    
    try:
        eel.js_on_rare_ping_blocked(payload)()
    except Exception as exc:
        print(f"[Engine] Could not show blocked rare-ping warning: {exc}")


def _close_blocked_rare_ping(pending_id):
    try:
        eel.js_on_rare_ping_resolved(str(pending_id))()
    except Exception:
        pass


def _show_biome_health_warning(payload):
    try:
        eel.js_on_biome_health_warning(payload)()
    except Exception as exc:
        print(f"[Engine] Could not show biome-health warning: {exc}")


def _close_biome_health_warning(acc_id):
    try:
        eel.js_on_biome_health_resolved(acc_id)()
    except Exception:
        pass


engine.rare_ping_notifier = _show_blocked_rare_ping
engine.rare_ping_resolver = _close_blocked_rare_ping
engine.biome_health_notifier = _show_biome_health_warning
engine.biome_health_resolver = _close_biome_health_warning


activity_log.account_provider = lambda: engine.automation.current_account
def _timeline_account_id(account_name):
    wanted = str(account_name or "").casefold()
    for account in config.accounts:
        if str(account.get("name") or "").casefold() == wanted:
            return account.get("id")
    return None


activity_log.account_id_provider = _timeline_account_id
activity_log.timeline_sink = account_timeline.record_activity
ram_trimmer = ram_trim.RamTrimmer(config, is_engine_running=lambda: engine.running)
throttler = throttle_mod.ThrottleEngine(
    config, is_engine_running=lambda: engine.running
)
engine.anti_afk.set_throttler(throttler)
engine.automation.set_throttler(throttler)
performance_benchmark = performance_benchmark_mod.PerformanceBenchmark(
    config, throttler
)

browser_login = browser_login_mod.BrowserLogin()

import atexit as _atexit
from core import webhooks as _webhooks

_atexit.register(throttler.stop)
_atexit.register(performance_benchmark.stop)
_atexit.register(roblox_auth.stop_account_launch_cleanup)
_atexit.register(roblox_auth.release_multi_instance)
_atexit.register(browser_login.cancel)
_atexit.register(lambda: _webhooks.flush(8.0))
_atexit.register(config.save_on_shutdown)


_hotkey_handle = None
_hotkey_lock = threading.Lock()

_mode_hotkey_handle = None
_mode_hotkey_lock = threading.Lock()

_maintenance_lock = threading.Lock()
_maintenance_active = False


def _start_engine_if_available():
    with _maintenance_lock:
        if _maintenance_active:
            return {
                "ok": False,
                "errors": [
                    "Roblox log cleanup is currently running. Wait for it to finish."
                ],
                "running": False,
            }
        return engine.start()


def _begin_maintenance():
    global _maintenance_active
    with _maintenance_lock:
        if _maintenance_active:
            return "busy"
        if engine.running:
            return "running"
        _maintenance_active = True
        return None


def _end_maintenance():
    global _maintenance_active
    with _maintenance_lock:
        _maintenance_active = False


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
            _mode_hotkey_handle = keyboard.add_hotkey(
                key, _on_mode_hotkey_triggered, suppress=True
            )
            print(f"[Hotkey] Registered mode toggle hotkey: {key}")
        except Exception as e:
            print(f"[Hotkey] Could not register mode hotkey '{key}': {e}")


def _on_hotkey_triggered():
    if engine.running:
        result = engine.stop()
        eel.js_on_hotkey_stop(result)()
    else:
        result = _start_engine_if_available()
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
            _hotkey_handle = keyboard.add_hotkey(
                key, _on_hotkey_triggered, suppress=True
            )
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
        eel.js_on_engine_sync(
            {
                "running": engine.running,
                "uptime": engine.uptime,
                "mode": config.automation.get("mode", "idle"),
            }
        )()
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
        "cyberspaceProgress": config.cyberspace_progress(),
        "edenStats": dict(config.eden_stats),
        "accountStates": engine.account_runtime(),
        "fishing": {
            **engine.automation.fishing.status(),
            "rotation": engine.automation.fishing.rotation_status(),
        },
        "timeTracking": engine.time.live(),
    }


@eel.expose
def get_engine_signal():
    module = engine.current_module()
    status = status_events.snapshot()




    if module.get("key") != "fishing":
        status.pop("detail", None)
    return {
        "running": engine.running,
        "uptime": engine.uptime,
        "module": module,
        "status": status,
    }


@eel.expose
def get_activity_log(since_id=0):
    return activity_log.since(since_id)


@eel.expose
def get_account_timeline(account_id=None, before_id=None, limit=250,
                         categories=None, search=None, kinds=None, since_ts=None):
    return account_timeline.get(
        account_id, before_id, limit, categories, search, kinds, since_ts
    )


@eel.expose
def clear_account_timeline(account_id=None):
    return account_timeline.clear(account_id)


@eel.expose
def get_biome_durations():
    from core import biomes as _biomes

    return dict(_biomes.BIOME_DURATIONS)


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
def clear_roblox_logs():
    blocked = _begin_maintenance()
    if blocked:
        return {
            "ok": False,
            "error": blocked,
            "closedInstances": 0,
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }
    try:
        return roblox_cleanup_mod.clear_logs()
    except Exception as error:
        print(f"[Roblox] Log cleanup failed: {error}")
        return {
            "ok": False,
            "error": "cleanup_failed",
            "closedInstances": 0,
            "deletedItems": 0,
            "remainingItems": 0,
            "failedFiles": [],
        }
    finally:
        _end_maintenance()


@eel.expose
def create_support_bundle():
    
    try:
        return support_bundle.create(
            config.dir,
            config.data,
            str(config.data.get("version") or "1.2.1"),
            dev_build="dev" in config.dir.name.casefold(),
        )
    except Exception as exc:
        print(f"[Support Bundle] Could not create archive: {exc}")
        return {"ok": False, "error": "create_failed"}


def _windows_search_dev_build() -> bool:
    
    return config.dir.name.casefold() == "solrich-dev"


@eel.expose
def get_windows_search_status():
    return windows_search.status(_windows_search_dev_build())


@eel.expose
def add_windows_search_shortcut():
    return windows_search.install(_windows_search_dev_build())


@eel.expose
def remove_windows_search_shortcut():
    return windows_search.uninstall(_windows_search_dev_build())


@eel.expose
def add_account(name, link=""):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    owner = config.account_name_owner(name)
    if owner:
        return {
            "ok": False,
            "error": f"duplicate_account:{owner.get('name', '')}",
            "state": _state_with_status(),
        }
    profile = MacroEngine.get_roblox_profile(name)
    try:
        config.add_account(
            name,
            link,
            profile.get("avatar", ""),
            roblox_user_id=profile.get("id"),
            roblox_username=profile.get("name", ""),
        )
    except ValueError:
        return {
            "ok": False,
            "error": "duplicate_account",
            "state": _state_with_status(),
        }
    return {"ok": True, "state": _state_with_status()}


@eel.expose
def update_account(acc_id, name=None, link=None):
    if _guard():
        return {"ok": False, "error": "running", "state": _state_with_status()}
    owner = (
        config.account_name_owner(name, exclude_id=acc_id) if name is not None else None
    )
    if owner:
        return {
            "ok": False,
            "error": f"duplicate_account:{owner.get('name', '')}",
            "state": _state_with_status(),
        }
    avatar = None
    profile = None
    existing = next((a for a in config.accounts if a.get("id") == acc_id), None)
    if existing and name and name.strip() != existing.get("name"):
        profile = MacroEngine.get_roblox_profile(name)
        avatar = profile.get("avatar", "")
    try:
        updated = config.update_account(acc_id, name=name, link=link, avatar=avatar)
    except ValueError:
        return {
            "ok": False,
            "error": "duplicate_account",
            "state": _state_with_status(),
        }
    if updated and profile is not None:
        config.set_account_profile(
            acc_id,
            profile.get("id"),
            profile.get("name", ""),
            avatar=profile.get("avatar", ""),
        )
    return {
        "ok": bool(updated),
        "error": None if updated else "no_account",
        "state": _state_with_status(),
    }


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
    general = (
        (config.automation.get("merchants", {}) or {}).get("calib", {}) or {}
    ).get("general", {}) or {}
    return _is_point(
        (general.get("pixels", {}) or {}).get("dialogue_skip")
    ) and _is_region((general.get("regions", {}) or {}).get("merchant_name"))




def _merchant_autobuy_calib_ready():
    
    import core.merchants_data as _md

    calib = (config.automation.get("merchants", {}) or {}).get("calib", {}) or {}

    def _points_ok(group):
        px = (calib.get(group, {}) or {}).get("pixels", {}) or {}
        return all(_is_point(px.get(k)) for k in _md.calib_point_keys(group))

    def _regions_ok(group):
        rg = (calib.get(group, {}) or {}).get("regions", {}) or {}
        keys = (
            _md.required_shop_region_keys()
            if group == "shop"
            else _md.calib_region_keys(group)
        )
        return all(_is_region(rg.get(k)) for k in keys)

    return (
        _points_ok("shop")
        and _regions_ok("shop")
        and _points_ok("mari")
        and _points_ok("jester")
    )


FISHING_REQUIRED_SLOTS = (
    "cast_point",
    "bite_indicator",
    "bar_sample",
    "zone_left",
    "zone_right",
    "reel_click",
    "claim_button",
)


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
        if (
            task in ("strangeController", "biomeRandomizer")
            and not _inventory_calib_ready()
        ):
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
    owner = config.token_owner(token, exclude_id=acc_id)
    if owner:
        return {
            "ok": False,
            "error": f"already_linked:{owner.get('name', '')}",
            "state": _state_with_status(),
        }
    info = roblox_auth.validate_token(token)
    if info.get("ok") or info.get("refreshed"):
        linked_owner = config.linked_user_owner(info.get("name", ""), exclude_id=acc_id)
        if linked_owner:
            return {
                "ok": False,
                "error": f"already_linked:{linked_owner.get('name', '')}",
                "state": _state_with_status(),
            }
        try:
            config.set_account_token(acc_id, info.get("refreshed") or token)
        except SecureStoreError:
            return {
                "ok": False,
                "error": "secure_storage_unavailable",
                "state": _state_with_status(),
                "security": config.token_security_status(),
            }
        config.set_account_token_status(
            acc_id, info.get("name", ""), True, info.get("id")
        )
        result = {
            "ok": True,
            "user": info.get("name", ""),
            "displayName": info.get("displayName", ""),
        }
    elif info.get("definitive"):


        result = {"ok": False, "error": info.get("error", "invalid")}
    else:
        try:
            config.set_account_token(acc_id, token)
        except SecureStoreError:
            return {
                "ok": False,
                "error": "secure_storage_unavailable",
                "state": _state_with_status(),
                "security": config.token_security_status(),
            }
        config.set_account_token_status(acc_id, "", True)
        result = {
            "ok": True,
            "user": "",
            "displayName": "",
            "unverified": True,
            "error": info.get("error"),
        }
    result["state"] = _state_with_status()
    result["security"] = config.token_security_status()
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
            owner = config.token_owner(token, exclude_id=acc_id)
            if owner:
                payload = f"already_linked:{owner.get('name', '')}"
                try:
                    eel.onBrowserLoginResult(acc_id, False, payload)()
                except Exception:
                    pass
                return
            info = roblox_auth.validate_token(token)
            store_token = info.get("refreshed") or token
            if info.get("ok") or info.get("refreshed"):
                tname = (info.get("name") or "").strip()
                dname = (info.get("displayName") or "").strip()
                want = (acc.get("name") or "").strip()
                linked_owner = config.linked_user_owner(tname, exclude_id=acc_id)
                if linked_owner:
                    payload = f"already_linked:{linked_owner.get('name', '')}"
                elif (
                    want
                    and tname
                    and want.lower() not in (tname.lower(), dname.lower())
                ):
                    payload = f"wrong_account:{tname}"
                else:
                    try:
                        config.set_account_token(acc_id, store_token)
                    except SecureStoreError:
                        payload = "secure_storage_unavailable"
                        try:
                            eel.onBrowserLoginResult(acc_id, False, payload)()
                        except Exception:
                            pass
                        return
                    config.set_account_token_status(
                        acc_id, tname, True, info.get("id")
                    )
                    ok, payload = True, tname
            elif info.get("definitive"):
                payload = info.get("error", "invalid")
            else:
                try:
                    config.set_account_token(acc_id, token)
                except SecureStoreError:
                    payload = "secure_storage_unavailable"
                    try:
                        eel.onBrowserLoginResult(acc_id, False, payload)()
                    except Exception:
                        pass
                    return
                config.set_account_token_status(
                    acc_id, (acc.get("name") or "").strip(), True
                )
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
    try:
        config.clear_account_token(acc_id)
    except SecureStoreError:
        return {"ok": False, "error": "delete_failed", "state": _state_with_status()}
    return {
        "ok": True,
        "state": _state_with_status(),
        "security": config.token_security_status(),
    }


@eel.expose
def get_token_security_status():
    
    return config.token_security_status()


@eel.expose
def clear_all_account_tokens():
    if _guard():
        return {
            "ok": False,
            "error": "running",
            "state": _state_with_status(),
            "security": config.token_security_status(),
        }
    try:
        removed = config.clear_all_account_tokens()
    except SecureStoreError:
        return {
            "ok": False,
            "error": "delete_failed",
            "state": _state_with_status(),
            "security": config.token_security_status(),
        }
    return {
        "ok": True,
        "removed": removed,
        "state": _state_with_status(),
        "security": config.token_security_status(),
    }


@eel.expose
def revalidate_account_token(acc_id):
    token = config.account_token(acc_id)
    if not token:
        return {"ok": False, "error": "no_token", "state": _state_with_status()}
    info = roblox_auth.validate_token(token)
    _apply_token_refresh(acc_id, info.get("refreshed"))
    if info.get("ok") or info.get("refreshed"):
        config.set_account_token_status(
            acc_id, info.get("name", ""), True, info.get("id")
        )
        return {"ok": True, "user": info.get("name", ""), "state": _state_with_status()}
    if info.get("definitive"):
        config.set_account_token_status(acc_id, "", False)
        return {"ok": False, "error": info.get("error"), "state": _state_with_status()}
    return {
        "ok": False,
        "transient": True,
        "error": info.get("error"),
        "state": _state_with_status(),
    }


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
def get_performance_benchmark():
    return performance_benchmark.status()


@eel.expose
def start_performance_benchmark():
    return performance_benchmark.start()


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
            timeout=10,
        )
        universe_id = r.json().get("universeId") if r.ok else None
        universe_name = ""
        owner_name = ""
        owner_type = ""
        thumb_url = ""
        if universe_id:
            r2 = _req.get(
                f"https://games.roblox.com/v1/games?universeIds={universe_id}",
                timeout=10,
            )
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
                timeout=10,
            )
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
    pid = info.get("pid")
    in_place = bool(hwnd and pid and sys.platform == "win32")

    if in_place:
        try:
            win_windows.focus_hwnd(hwnd)
        except Exception:
            pass
        if roblox_auth.teleport_in_place(place_info):
            acc["launchTime"] = time.time()
            config.save()
            return {"ok": True, "method": "in_place", "rebound": True}
        return {"ok": False, "error": "deeplink_failed"}

    tmp = dict(acc)
    tmp["link"] = link
    tmp["token"] = token
    res = roblox_auth.launch_account(tmp, mode="private")
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error", "launch_failed")}
    acc["launchTime"] = time.time()
    config.save()
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
        config.save()
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
        config.save()
    return res


@eel.expose
def get_account_windows():
    
    from core import win_windows

    bindings_before = {
        a.get("id"): dict(a.get("windowBinding"))
        for a in config.accounts
        if isinstance(a.get("windowBinding"), dict)
    }
    try:


        resolved = win_windows.resolve_accounts(config.accounts)
    except Exception as e:
        print(f"[Windows] Idle resolve failed: {e}")
        resolved = {}
    bindings_after = {
        a.get("id"): dict(a.get("windowBinding"))
        for a in config.accounts
        if isinstance(a.get("windowBinding"), dict)
    }
    if bindings_after != bindings_before:
        config.save()
    out = []
    for a in config.accounts:
        aid = a.get("id")
        if not a.get("enabled", True):
            out.append(
                {
                    "id": aid,
                    "online": False,
                    "currentBiome": None,
                    "window": None,
                    "hwndKnown": False,
                }
            )
            continue
        info = resolved.get(aid, {})
        out.append(
            {
                "id": aid,
                "online": bool(info.get("online")),
                "currentBiome": None,
                "window": info.get("label"),
                "hwndKnown": info.get("hwnd") is not None,
            }
        )
    return out


@eel.expose
def launch_all_accounts(mode="home"):
    results = []
    launched = 0
    for acc in config.enabled_accounts():
        token = config.account_token(acc.get("id"))
        if not token:
            results.append(
                {
                    "id": acc.get("id"),
                    "name": acc.get("name"),
                    "ok": False,
                    "error": "no_token",
                }
            )
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
            config.save()
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
        hwnd, pid = win_windows.hwnd_from_click(
            timeout=30.0, cancel_flag=lambda: _bind_cancel.is_set()
        )
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
    if key in (
        "throttleEnabled",
        "throttleMethod",
        "throttleCycleMs",
        "throttleQuota",
        "throttleFocusAware",
        "throttleOnlyWhenRunning",
        "throttleScope",
        "throttleBreathe",
        "throttleRamCap",
        "throttleRamCapMb",
        "throttleAccounts",
    ):
        throttler.sync()
    if key in (
        "antiAfkStandalone",
        "antiAfkEnabled",
        "antiAfkInterval",
        "antiAfkAction",
    ):
        engine.refresh_anti_afk()
    if key in ("monitorDimEnabled", "monitorDimLevel") and engine.running:
        if config.settings.get("monitorDimEnabled"):
            monitor_dim.start(config.settings.get("monitorDimLevel", 40))
        else:
            monitor_dim.stop()
    _broadcast_settings_sync()
    return _state_with_status()


@eel.expose
def save_custom_theme_background(data_url):
    from core import custom_theme

    return custom_theme.save_background(config, data_url)


@eel.expose
def get_custom_theme_background():
    from core import custom_theme

    return custom_theme.load_background(config)


@eel.expose
def clear_custom_theme_background():
    from core import custom_theme

    return custom_theme.clear_background(config)


@eel.expose
def test_clip_hotkey():
    
    return engine.clipping.test_hotkey()




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
def get_display_calibration_info():
    
    import core.merchant_presets as _merchant_presets
    import core.extra_presets as _extra_presets

    names = list(dict.fromkeys(
        presets.preset_names()
        + fishing_presets.preset_names()
        + _merchant_presets.preset_names()
        + _extra_presets.preset_names()
    ))
    return display_calibration.inspect_displays(names)


@eel.expose
def apply_recommended_calibration_preset():
    
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    info = get_display_calibration_info()
    name = info.get("preset")
    if not info.get("ok") or not name:
        return {**info, "ok": False, "error": info.get("reason") or "no_preset"}

    applied = {
        "automation": config.load_preset_pixels(name),
        "fishing": config.load_fishing_preset(name),
        "merchants": config.load_merchant_preset(name),
        "extra": config.load_extra_preset(name),
    }
    return {
        **info,
        "ok": any(applied.values()),
        "applied": applied,
        "error": None if any(applied.values()) else "preset_empty",
    }


@eel.expose
def load_automation_preset(name):
    if _guard():
        return _state_with_status()
    config.load_preset_pixels(name)
    return _state_with_status()


_CALIBRATION_GUIDE_ACCENTS = (
    "#6d84eb",
    "#38c5dd",
    "#3ecf8e",
    "#ee6a7c",
    "#e8a33d",
    "#e072b4",
    "#a184ef",
    "#d3d7e0",
    "#4e63ec",
)


def _show_calibration_guide(
    scope,
    slot,
    *,
    group=None,
    is_region=False,
    step=1,
    focus_window=False,
):
    
    if focus_window and not focus_roblox():
        return {"ok": False, "error": "roblox_not_found"}

    guide = calibration_guides.build_guide(
        scope,
        slot,
        group=group,
        is_region=is_region,
        step=step,
    )
    try:
        accent_index = int(config.settings.get("accentIndex", 0))
    except (TypeError, ValueError):
        accent_index = 0
    if not 0 <= accent_index < len(_CALIBRATION_GUIDE_ACCENTS):
        accent_index = 0
    guide["accent"] = _CALIBRATION_GUIDE_ACCENTS[accent_index]

    roblox_window = win_windows.foreground_hwnd()
    window_rect = win_windows.window_rect(roblox_window)
    if window_rect:
        guide["anchorRect"] = list(window_rect)
    shown = overlay.show_calibration_guide(guide, duration=None)
    if shown.get("ok") and roblox_window:


        win_windows.focus_hwnd(roblox_window)
    return shown


def _capture_guided_point(scope, slot, *, group=None, timeout=30.0):
    shown = _show_calibration_guide(
        scope,
        slot,
        group=group,
        focus_window=True,
    )
    if not shown.get("ok"):
        return None, shown.get("error", "guide_failed")

    from core import calibration_magnifier

    calibration_magnifier.show()

    try:
        position = engine.automation._capture_click(timeout=timeout)
        return position, None if position else "timeout"
    finally:
        calibration_magnifier.hide()
        overlay.hide_calibration_guide()


def _capture_guided_region(scope, slot, *, group=None, timeout=30.0):
    shown = _show_calibration_guide(
        scope,
        slot,
        group=group,
        is_region=True,
        step=1,
        focus_window=True,
    )
    if not shown.get("ok"):
        return None, None, shown.get("error", "guide_failed")

    from core import calibration_magnifier

    calibration_magnifier.show()

    try:
        top_left = engine.automation._capture_click(timeout=timeout)
        if not top_left:
            return None, None, "timeout"

        _show_calibration_guide(
            scope,
            slot,
            group=group,
            is_region=True,
            step=2,
        )
        bottom_right = engine.automation._capture_click(timeout=timeout)
        if not bottom_right:
            return top_left, None, "timeout"
        return top_left, bottom_right, None
    finally:
        calibration_magnifier.hide()
        overlay.hide_calibration_guide()


@eel.expose
def capture_item_region():

    if _guard():
        return {"ok": False, "error": "tracking_active"}
    p1, p2, error = _capture_guided_region("automation", "first_item_region")
    if error:
        return {"ok": False, "error": error}
    config.set_first_item_region(p1, p2)
    x = min(p1[0], p2[0])
    y = min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])
    print(
        f"[Calibration] Item region set → ({x},{y}) {w}×{h}px, click centre ({x + w // 2},{y + h // 2})"
    )
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
    if slot not in presets.slot_keys():
        return {"ok": False, "error": "bad_slot"}
    position, error = _capture_guided_point("automation", slot)
    if error:
        return {"ok": False, "error": error}
    config.set_pixel(slot, [position[0], position[1]])
    print(f"[Automation] Captured '{slot}' → {position[0]}, {position[1]}")
    return {
        "ok": True,
        "slot": slot,
        "x": position[0],
        "y": position[1],
    }


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
    if slot not in fishing_presets.slot_keys():
        return {"ok": False, "error": "bad_slot"}
    position, error = _capture_guided_point("fishing", slot)
    if error:
        return {"ok": False, "error": error}
    config.set_fishing_pixel(slot, [position[0], position[1]])
    print(f"[Fishing] Captured '{slot}' → {position[0]}, {position[1]}")
    return {
        "ok": True,
        "slot": slot,
        "x": position[0],
        "y": position[1],
    }


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
    p1, p2, error = _capture_guided_region("fishing", name)
    if error:
        return {"ok": False, "error": error}
    config.set_fishing_region(name, p1, p2)
    x = min(p1[0], p2[0])
    y = min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])
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
    position, error = _capture_guided_point("merchant", slot, group=group)
    if error:
        return {"ok": False, "error": error}
    config.set_merchant_pixel(group, slot, [position[0], position[1]])
    print(f"[Calibration] Merchant '{group}/{slot}' → {position[0]}, {position[1]}")
    return {
        "ok": True,
        "group": group,
        "slot": slot,
        "x": position[0],
        "y": position[1],
    }


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
    p1, p2, error = _capture_guided_region("merchant", name, group=group)
    if error:
        return {"ok": False, "error": error}
    config.set_merchant_region(group, name, p1, p2)
    x = min(p1[0], p2[0])
    y = min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])
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
    position, error = _capture_guided_point("extra", slot, group=group)
    if error:
        return {"ok": False, "error": error}
    config.set_extra_pixel(group, slot, [position[0], position[1]])
    print(f"[Calibration] Extra '{group}/{slot}' → {position[0]}, {position[1]}")
    return {
        "ok": True,
        "group": group,
        "slot": slot,
        "x": position[0],
        "y": position[1],
    }


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
    p1, p2, error = _capture_guided_region("extra", name, group=group)
    if error:
        return {"ok": False, "error": error}
    config.set_extra_region(group, name, p1, p2)
    x = min(p1[0], p2[0])
    y = min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])
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
    return {"biomes": _ap.biome_keys(), "unknown": ["unknown:" + n for n in unknown]}


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
    p1, p2, error = _capture_guided_region("autopop", "amount_label")
    if error:
        return {"ok": False, "error": error}
    config.set_autopop_amount_region(p1, p2)
    x = min(p1[0], p2[0])
    y = min(p1[1], p2[1])
    w = abs(p2[0] - p1[0])
    h = abs(p2[1] - p1[1])
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
    result = _start_engine_if_available()
    _broadcast_engine_sync()
    return result


@eel.expose
def stop_macro():
    result = engine.stop()
    _broadcast_engine_sync()
    return result


@eel.expose
def confirm_blocked_rare_ping(pending_id):
    
    return engine.confirm_blocked_rare_ping(pending_id)


@eel.expose
def dismiss_blocked_rare_ping(pending_id):
    
    return engine.dismiss_blocked_rare_ping(pending_id)


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
    "shop": "#fb923c",
    "mari": "#a855f7",
    "jester": "#22d3ee",
    "rin": "#34d399",
}


def _collect_merchant_points():
    import core.merchants_data as _md

    auto = config.automation
    calib = (auto.get("merchants", {}) or {}).get("calib", {}) or {}
    points = []
    for group in _md.calib_groups():
        gkey = group["key"]
        color = _MERCHANT_GROUP_COLORS.get(gkey, "#f59e0b")
        gpix = (calib.get(gkey, {}) or {}).get("pixels", {}) or {}
        for slot, label in group.get("points", []):
            pos = gpix.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append(
                    {
                        "x": pos[0],
                        "y": pos[1],
                        "label": f"{group['label']}: {label}",
                        "color": color,
                    }
                )
    return points


def _collect_merchant_regions():
    import core.merchants_data as _md

    auto = config.automation
    calib = (auto.get("merchants", {}) or {}).get("calib", {}) or {}
    regions = []
    for group in _md.calib_groups():
        gkey = group["key"]
        color = _MERCHANT_GROUP_COLORS.get(gkey, "#f59e0b")
        grgn = (calib.get(gkey, {}) or {}).get("regions", {}) or {}
        for name, label in group.get("regions", []):
            box = grgn.get(name)
            if isinstance(box, (list, tuple)) and len(box) == 4:
                regions.append(
                    {
                        "x": box[0],
                        "y": box[1],
                        "w": box[2],
                        "h": box[3],
                        "label": f"{group['label']}: {label}",
                        "color": color,
                    }
                )
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
                points.append(
                    {
                        "x": pos[0],
                        "y": pos[1],
                        "label": f"{group['label']}: {label}",
                        "color": color,
                    }
                )
        for sg in group.get("subgroups", []):
            for slot, label in sg.get("points", []):
                pos = gpix.get(slot)
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    points.append(
                        {
                            "x": pos[0],
                            "y": pos[1],
                            "label": f"{group['label']}: {sg['label']}: {label}",
                            "color": color,
                        }
                    )
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
                regions.append(
                    {
                        "x": box[0],
                        "y": box[1],
                        "w": box[2],
                        "h": box[3],
                        "label": f"{group['label']}: {label}",
                        "color": color,
                    }
                )
        for sg in group.get("subgroups", []):
            for name, label in sg.get("regions", []):
                box = grgn.get(name)
                if isinstance(box, (list, tuple)) and len(box) == 4:
                    regions.append(
                        {
                            "x": box[0],
                            "y": box[1],
                            "w": box[2],
                            "h": box[3],
                            "label": f"{group['label']}: {sg['label']}: {label}",
                            "color": color,
                        }
                    )
    return regions


_VALID_CALIBRATION_SCOPES = {
    "automation",
    "fishing",
    "merchants",
    "chat",
    "eden",
    "aura_storage",
    "fischl",
    "crafting",
    "loading_screen",
    "ps_check",
    "all",
}


def _collect_points(scope):
    auto = config.automation
    points = []
    if scope in ("automation", "all"):
        pixels = auto.get("pixels", {}) or {}
        for slot, label in _auto_presets.PIXEL_SLOTS:
            pos = pixels.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append(
                    {"x": pos[0], "y": pos[1], "label": label, "color": "#4f6ef7"}
                )
    if scope in ("merchants", "all"):
        points.extend(_collect_merchant_points())
    if scope in ("fishing", "all"):
        fpixels = (auto.get("fishing", {}) or {}).get("pixels", {}) or {}
        for slot, label in _fish_presets.PIXEL_SLOTS:
            pos = fpixels.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                points.append(
                    {"x": pos[0], "y": pos[1], "label": label, "color": "#22d3ee"}
                )
    if scope in (
        "chat",
        "eden",
        "aura_storage",
        "fischl",
        "crafting",
        "loading_screen",
        "ps_check",
        "all",
    ):
        import core.extra_calibrations as _ec

        all_pts = _collect_extra_points()
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
                        points.append(
                            {"x": pos[0], "y": pos[1], "label": label, "color": color}
                        )
                for sg in g.get("subgroups", []):
                    for slot, label in sg.get("points", []):
                        pos = gpix.get(slot)
                        if isinstance(pos, (list, tuple)) and len(pos) == 2:
                            points.append(
                                {
                                    "x": pos[0],
                                    "y": pos[1],
                                    "label": f"{sg['label']}: {label}",
                                    "color": color,
                                }
                            )
    return points


def _collect_regions(scope):
    auto = config.automation
    regions = []
    if scope in ("automation", "all"):
        item = auto.get("firstItemRegion")
        if isinstance(item, (list, tuple)) and len(item) == 4:
            regions.append(
                {
                    "x": item[0],
                    "y": item[1],
                    "w": item[2],
                    "h": item[3],
                    "label": "First Item Region",
                    "color": "#4f6ef7",
                }
            )
    if scope in ("merchants", "all"):
        regions.extend(_collect_merchant_regions())
    if scope in ("fishing", "all"):
        fregions = (auto.get("fishing", {}) or {}).get("regions", {}) or {}
        for nm, box in fregions.items():
            if isinstance(box, (list, tuple)) and len(box) == 4:
                regions.append(
                    {
                        "x": box[0],
                        "y": box[1],
                        "w": box[2],
                        "h": box[3],
                        "label": _fish_presets.region_label(nm),
                        "color": "#22d3ee",
                    }
                )
    if scope in (
        "chat",
        "eden",
        "aura_storage",
        "fischl",
        "crafting",
        "loading_screen",
        "ps_check",
        "all",
    ):
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
                        regions.append(
                            {
                                "x": box[0],
                                "y": box[1],
                                "w": box[2],
                                "h": box[3],
                                "label": label,
                                "color": color,
                            }
                        )
                for sg in g.get("subgroups", []):
                    for name, label in sg.get("regions", []):
                        box = grgn.get(name)
                        if isinstance(box, (list, tuple)) and len(box) == 4:
                            regions.append(
                                {
                                    "x": box[0],
                                    "y": box[1],
                                    "w": box[2],
                                    "h": box[3],
                                    "label": f"{sg['label']}: {label}",
                                    "color": color,
                                }
                            )
    return regions


@eel.expose
def show_calibration_points(scope="all", duration=4.0):
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    norm = scope if scope in _VALID_CALIBRATION_SCOPES else "all"
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
def start_calibration_test(scope="automation"):
    
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    norm = scope if scope in _VALID_CALIBRATION_SCOPES else "automation"
    points = _collect_points(norm)
    regions = _collect_regions(norm)
    if not points and not regions:
        return {"ok": False, "error": "no_points", "scope": norm, "count": 0}
    result = overlay.show_points(points, None, regions=regions)
    return {
        **result,
        "scope": norm,
        "count": len(points) + len(regions),
        "points": len(points),
        "regions": len(regions),
    }


@eel.expose
def stop_calibration_test():
    
    return overlay.hide_points()






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
        region_keys = (
            fishing_presets.region_keys()
        )
        label = "fishing"
    elif scope == "merchants":
        return _merchant_calibration_text()
    elif scope == "all":
        from core import calibration_transfer

        return calibration_transfer.export_text(config.automation)
    elif scope in (
        "chat",
        "eden",
        "aura_storage",
        "fischl",
        "crafting",
        "loading_screen",
        "ps_check",
    ):
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
            lines.append(
                f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],'
            )
        else:
            lines.append(f'        "{name}": None,')
    lines.append("    },")
    return "\n".join(lines)


def _public_calibration_report(report):
    return {
        key: value
        for key, value in report.items()
        if key != "normalized"
    }


@eel.expose
def preview_calibration_import(text):
    
    from core import calibration_transfer

    return _public_calibration_report(calibration_transfer.inspect_text(text))


@eel.expose
def apply_calibration_import(text):
    
    if _guard():
        return {"ok": False, "error": "tracking_active", "canApply": False}
    from core import calibration_transfer

    report = calibration_transfer.inspect_text(text)
    if not report.get("ok") or not report.get("canApply"):
        return _public_calibration_report(report)
    with config._lock:
        applied = calibration_transfer.apply_to_automation(
            config.automation,
            report.get("normalized") or {},
        )
        config.save()
    return {
        **_public_calibration_report(report),
        "ok": True,
        "appliedCount": applied,
    }


@eel.expose
def set_calibration_value(scope, key, value, group=None):
    
    if _guard():
        return {"ok": False, "error": "tracking_active"}
    selected_scope = str(scope or "").strip().casefold()
    selected_key = str(key or "").strip()
    selected_group = str(group or "").strip()

    expected = None
    if selected_scope == "inventory":
        if selected_key in presets.slot_keys():
            expected = 2
        elif selected_key in {"first_item_region", "autopop_amount_region"}:
            expected = 4
    elif selected_scope == "fishing":
        if selected_key in fishing_presets.slot_keys():
            expected = 2
        elif selected_key in fishing_presets.region_keys():
            expected = 4
    elif selected_scope == "merchants":
        import core.merchants_data as _md

        if selected_group in _md.calib_group_keys():
            if selected_key in _md.calib_point_keys(selected_group):
                expected = 2
            elif selected_key in _md.calib_region_keys(selected_group):
                expected = 4
    elif selected_scope == "extra":
        import core.extra_calibrations as _ec

        if _ec.group(selected_group):
            if selected_key in _ec.point_keys(selected_group):
                expected = 2
            elif selected_key in _ec.region_keys(selected_group):
                expected = 4

    if expected is None:
        return {"ok": False, "error": "unknown_calibration"}
    if not isinstance(value, (list, tuple)) or len(value) != expected:
        return {"ok": False, "error": "invalid_coordinate"}
    try:
        clean = [int(round(float(item))) for item in value]
    except (TypeError, ValueError, OverflowError):
        return {"ok": False, "error": "invalid_coordinate"}
    if expected == 4 and (clean[2] <= 0 or clean[3] <= 0):
        return {"ok": False, "error": "invalid_coordinate"}

    def corners(box):
        x, y, width, height = box
        return [x, y], [x + width, y + height]

    if selected_scope == "inventory":
        if selected_key == "first_item_region":
            config.set_first_item_region(*corners(clean))
        elif selected_key == "autopop_amount_region":
            config.set_autopop_amount_region(*corners(clean))
        else:
            config.set_pixel(selected_key, clean)
    elif selected_scope == "fishing":
        if expected == 2:
            config.set_fishing_pixel(selected_key, clean)
        else:
            config.set_fishing_region(selected_key, *corners(clean))
    elif selected_scope == "merchants":
        if expected == 2:
            config.set_merchant_pixel(selected_group, selected_key, clean)
        else:
            config.set_merchant_region(selected_group, selected_key, *corners(clean))
    else:
        if expected == 2:
            config.set_extra_pixel(selected_group, selected_key, clean)
        else:
            config.set_extra_region(selected_group, selected_key, *corners(clean))
    return {"ok": True, "value": clean}


def _extra_calibration_text(scope):
    import core.extra_calibrations as _ec

    g = _ec.group(scope)
    if not g:
        return ""
    calib = config.automation.get("calib", {}) or {}
    gdata = calib.get(scope, {}) or {}
    gpix = gdata.get("pixels", {}) or {}
    grgn = gdata.get("regions", {}) or {}
    lines = [
        f"# SolRich {g['label']} calibration",
        '    "MY RESOLUTION (rename me)": {',
    ]
    for slot, _lbl in g.get("points", []):
        v = gpix.get(slot)
        lines.append(
            f'        "{slot}": [{int(v[0])}, {int(v[1])}],'
            if isinstance(v, (list, tuple)) and len(v) == 2
            else f'        "{slot}": None,'
        )
    for name, _lbl in g.get("regions", []):
        v = grgn.get(name)
        lines.append(
            f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],'
            if isinstance(v, (list, tuple)) and len(v) == 4
            else f'        "{name}": None,'
        )
    for sg in g.get("subgroups", []):
        lines.append(f"        # {sg['label']}")
        for slot, _lbl in sg.get("points", []):
            v = gpix.get(slot)
            lines.append(
                f'        "{slot}": [{int(v[0])}, {int(v[1])}],'
                if isinstance(v, (list, tuple)) and len(v) == 2
                else f'        "{slot}": None,'
            )
        for name, _lbl in sg.get("regions", []):
            v = grgn.get(name)
            lines.append(
                f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],'
                if isinstance(v, (list, tuple)) and len(v) == 4
                else f'        "{name}": None,'
            )
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
        parts.append(f"\n# == {g['label']} ==")
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

    calib = (config.automation.get("merchants", {}) or {}).get("calib", {}) or {}
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
                lines.append(
                    f'        "{name}": [{int(v[0])}, {int(v[1])}, {int(v[2])}, {int(v[3])}],'
                )
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




@eel.expose
def get_aura_log(since_id=0):
    
    try:
        return engine.aura.aura_log(int(since_id or 0))
    except Exception:
        return []






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



    dev_ui_url = None
    ui_port = 0
    ui_debug = False


    for mode in browser_modes:
        try:
            print(f"[SolRich] Trying to run app in '{mode}' mode...")

            cmd_args = []
            if mode in ["chrome", "edge"]:
                cmd_args = [
                    f"--user-data-dir={profile_dir}",
                    "--no-first-run",
                    "--new-window",
                ]

            eel.start(
                "index.html",
                size=(1080, 720),
                mode=mode,
                cmdline_args=cmd_args,
                port=ui_port,
                open_url=dev_ui_url,
                debug=ui_debug,
                on_close=overlay.hide_calibration_guide,
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
