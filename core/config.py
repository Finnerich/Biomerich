import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from . import biomes

APP_FOLDER = "Biomerich"
CONFIG_FILENAME = "config.json"

def get_config_dir() -> Path:
    base = os.getenv("LOCALAPPDATA")
    if not base:
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = Path(base) / APP_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path

def _default_automation() -> dict:
    return {
        "mode": "idle",
        "biomeRandomizer": False,
        "strangeController": False,
        "preset": "",
        "amount": "1",
        "pixels": {
            "inventory_button": None,
            "item_tab": None,
            "search_bar": None,
            "first_item_slot": None,
            "amount_box": None,
            "use_button": None,
        },
        "intervals": {
            "strangeController": 21 * 60,
            "biomeRandomizer": 36 * 60,
        },
        "searchTerms": {
            "strangeController": "Strange Controller",
            "biomeRandomizer": "Biome Randomizer",
        },
    }

def _default_config() -> dict:
    return {
        "version": "0.1.4",
        "accounts": [],
        "webhooks": [],
        "biomeCounts": biomes.empty_counts(),
        "unknownBiomes": {},
        "settings": {
            "accentIndex": 0,
            "firstStartDone": True,
            "antiAfkEnabled": False,
            "antiAfkAction": "space",
            "antiAfkInterval": 300,
            "hotkey": "F5",
        },
        "automation": _default_automation(),
    }

class ConfigManager:
    def __init__(self):
        self.dir = get_config_dir()
        self.path = self.dir / CONFIG_FILENAME
        self._lock = threading.RLock()
        self.data = self._load()

    def _load(self) -> dict:
        cfg = _default_config()
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                for key in ("accounts", "webhooks", "settings"):
                    if key in saved:
                        if isinstance(cfg[key], dict):
                            cfg[key].update(saved[key])
                        else:
                            cfg[key] = saved[key]

                saved_auto = saved.get("automation")
                if isinstance(saved_auto, dict):
                    auto = cfg["automation"]
                    for k, v in saved_auto.items():
                        if isinstance(auto.get(k), dict) and isinstance(v, dict):
                            auto[k].update(v)
                        else:
                            auto[k] = v
                for k, v in (saved.get("biomeCounts") or {}).items():
                    if k in cfg["biomeCounts"] and isinstance(v, (int, float)):
                        cfg["biomeCounts"][k] = int(v)
                for name, v in (saved.get("unknownBiomes") or {}).items():
                    if isinstance(v, (int, float)):
                        cfg["unknownBiomes"][str(name)] = int(v)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Config] Couldnt read config.json ({e}) – using Defaults.")
        return cfg

    def save(self) -> None:
        with self._lock:
            try:
                fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
            except OSError as e:
                print(f"[Config] Saving failed: {e}")

    @property
    def accounts(self) -> list:
        return self.data["accounts"]

    @property
    def webhooks(self) -> list:
        return self.data["webhooks"]

    @property
    def biome_counts(self) -> dict:
        return self.data["biomeCounts"]

    @property
    def unknown_biomes(self) -> dict:
        return self.data["unknownBiomes"]

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def automation(self) -> dict:
        return self.data.setdefault("automation", _default_automation())

    def state(self) -> dict:
        with self._lock:
            return {
                "version": self.data.get("version", "?"),
                "accounts": [dict(a) for a in self.accounts],
                "webhooks": [dict(w) for w in self.webhooks],
                "biomeCounts": dict(self.biome_counts),
                "unknownBiomes": dict(self.unknown_biomes),
                "settings": dict(self.settings),
                "automation": json.loads(json.dumps(self.automation)),
            }

    def _find(self, items, item_id):
        return next((x for x in items if x.get("id") == item_id), None)

    def add_account(self, name: str, link: str = "", avatar: str = "", acc_id=None) -> dict:
        with self._lock:
            acc = {
                "id": acc_id or self._new_id(),
                "name": name.strip(),
                "link": (link or "").strip(),
                "avatar": avatar or "",
            }
            self.accounts.append(acc)
            self.save()
            return acc

    def update_account(self, acc_id, name=None, link=None, avatar=None) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            if name is not None:
                acc["name"] = name.strip()
            if link is not None:
                acc["link"] = link.strip()
            if avatar is not None:
                acc["avatar"] = avatar
            self.save()
            return True

    def delete_account(self, acc_id) -> bool:
        with self._lock:
            before = len(self.accounts)
            self.data["accounts"] = [a for a in self.accounts if a.get("id") != acc_id]
            for w in self.webhooks:
                w["routedAccounts"] = [i for i in w.get("routedAccounts", []) if i != acc_id]
            self.save()
            return len(self.accounts) != before

    def add_webhook(self, name: str, url: str) -> dict:
        with self._lock:
            wh = {
                "id": self._new_id(),
                "name": name.strip(),
                "url": url.strip(),
                "active": True,
                "routedAccounts": [],
            }
            self.webhooks.append(wh)
            self.save()
            return wh

    def update_webhook(self, wh_id, name=None, url=None) -> bool:
        with self._lock:
            wh = self._find(self.webhooks, wh_id)
            if not wh:
                return False
            if name is not None:
                wh["name"] = name.strip()
            if url is not None:
                wh["url"] = url.strip()
            self.save()
            return True

    def delete_webhook(self, wh_id) -> bool:
        with self._lock:
            before = len(self.webhooks)
            self.data["webhooks"] = [w for w in self.webhooks if w.get("id") != wh_id]
            self.save()
            return len(self.webhooks) != before

    def set_webhook_active(self, wh_id, active: bool) -> bool:
        with self._lock:
            wh = self._find(self.webhooks, wh_id)
            if not wh:
                return False
            wh["active"] = bool(active)
            self.save()
            return True

    def set_routing(self, wh_id, acc_id, enabled: bool) -> bool:
        with self._lock:
            wh = self._find(self.webhooks, wh_id)
            if not wh:
                return False
            routed = wh.setdefault("routedAccounts", [])
            if enabled and acc_id not in routed:
                routed.append(acc_id)
            elif not enabled and acc_id in routed:
                routed.remove(acc_id)
            self.save()
            return True

    def set_setting(self, key: str, value) -> None:
        with self._lock:
            self.settings[key] = value
            self.save()

    def set_automation(self, key: str, value) -> None:
        with self._lock:
            self.automation[key] = value
            self.save()

    def set_automation_task(self, task: str, enabled: bool) -> None:
        if task not in ("strangeController", "biomeRandomizer"):
            return
        with self._lock:
            self.automation[task] = bool(enabled)
            self.save()

    def set_search_term(self, task: str, term: str) -> None:
        if task not in ("strangeController", "biomeRandomizer"):
            return
        with self._lock:
            terms = self.automation.setdefault("searchTerms", {})
            terms[task] = (term or "").strip()
            self.save()

    def set_amount(self, value: str) -> None:
        with self._lock:
            v = "".join(ch for ch in str(value) if ch.isdigit()) or "1"
            self.automation["amount"] = v
            self.save()

    def set_pixel(self, slot: str, xy) -> None:
        with self._lock:
            pixels = self.automation.setdefault("pixels", {})
            if xy is None:
                pixels[slot] = None
            else:
                pixels[slot] = [int(xy[0]), int(xy[1])]
            self.save()

    def load_preset_pixels(self, name: str) -> bool:
        from . import presets
        coords = presets.get_preset(name)
        if not coords:
            return False
        with self._lock:
            pixels = self.automation.setdefault("pixels", {})
            for slot, pos in coords.items():
                pixels[slot] = [int(pos[0]), int(pos[1])]
            self.automation["preset"] = name
            self.save()
            return True

    def increment_biome(self, key: str) -> None:
        with self._lock:
            if key in self.biome_counts:
                self.biome_counts[key] += 1
                self.save()

    def increment_unknown(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        with self._lock:
            self.unknown_biomes[name] = self.unknown_biomes.get(name, 0) + 1
            self.save()

    _last_id = 0

    def _new_id(self) -> int:
        import time
        with self._lock:
            candidate = int(time.time() * 1000)
            existing = {x.get("id", 0) for x in self.accounts} | {
                x.get("id", 0) for x in self.webhooks
            }
            base = max(candidate, ConfigManager._last_id, *existing) if existing else max(candidate, ConfigManager._last_id)
            new_id = base + 1
            ConfigManager._last_id = new_id
            return new_id