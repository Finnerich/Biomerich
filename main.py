import webbrowser

import eel

import os
import threading

try:
    import keyboard
    _KEYBOARD_AVAILABLE = True
except ImportError:
    _KEYBOARD_AVAILABLE = False
    print("[Hotkey] 'keyboard' module not found. Install with: pip install keyboard")

from core import ConfigManager, MacroEngine, updater, presets

eel.init("web")

config = ConfigManager()
engine = MacroEngine(config)

_hotkey_handle = None
_hotkey_lock = threading.Lock()

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
            _hotkey_handle = keyboard.add_hotkey(key, _on_hotkey_triggered, suppress=False)
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

@eel.expose
def get_state():
    return _state_with_status()

@eel.expose
def get_status():
    return {
        "running": engine.running,
        "uptime": engine.uptime,
        "biomeCounts": dict(config.biome_counts),
        "unknownBiomes": dict(config.unknown_biomes),
        "accountStates": engine.account_states(),
    }

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
def set_setting(key, value):
    if key == "antiAfkEnabled" and engine.running:
        return _state_with_status()
    config.set_setting(key, value)
    if key == "hotkey":
        _register_hotkey(str(value))
    return _state_with_status()

@eel.expose
def set_automation_mode(mode):
    engine.set_automation_mode(mode)
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
def start_macro():
    return engine.start()

@eel.expose
def stop_macro():
    return engine.stop()

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

if __name__ == "__main__":
    print(f"[Finnerich] Config folder: {config.dir}")

    saved_hotkey = config.settings.get("hotkey", "F5")
    _register_hotkey(saved_hotkey)

    profile_dir = os.path.join(config.dir, "web_profile")

    browser_modes = ["chrome", "edge", "default"]

    for mode in browser_modes:
        try:
            print(f"[Biomerich] Trying to run app in '{mode}' mode...")

            cmd_args = []
            if mode in ["chrome", "edge"]:
                cmd_args = [
                    f'--user-data-dir={profile_dir}',
                    '--no-first-run',
                ]

            eel.start(
                "index.html",
                size=(900, 900),
                mode=mode,
                cmdline_args=cmd_args,
                port=0
            )

            break

        except (EnvironmentError, ValueError) as e:
            print(f"[Biomerich] Mode '{mode}' failed. Trying next mode...")
            continue

        except (SystemExit, MemoryError, KeyboardInterrupt):
            engine.stop()
            break