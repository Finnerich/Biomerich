import webbrowser

import eel

import os

from core import ConfigManager, MacroEngine, updater

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
eel.init("web")

config = ConfigManager()
engine = MacroEngine(config)


def _state_with_status() -> dict:
    state = config.state()
    state["running"] = engine.running
    state["uptime"] = engine.uptime
    return state


def _guard():
    return engine.running


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@eel.expose
def set_setting(key, value):
    config.set_setting(key, value)
    return _state_with_status()


# ---------------------------------------------------------------------------
# Engine Start / Stop
# ---------------------------------------------------------------------------
@eel.expose
def start_macro():
    return engine.start()


@eel.expose
def stop_macro():
    return engine.stop()


@eel.expose
def get_roblox_avatar(username):
    return MacroEngine.get_roblox_avatar(username)


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[Finnerich] Config folder: {config.dir}")
    profile_dir = os.path.join(config.dir, "web_profile")
    
    try:
        eel.start(
            "index.html",
            size=(900, 900),
            mode="chrome",
            cmdline_args=[
                f'--user-data-dir={profile_dir}',
                '--no-first-run',
            ],
            port=0
        )
        
    except (SystemExit, MemoryError, KeyboardInterrupt):
        engine.stop()