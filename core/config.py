import json
import os
import shutil
import sys
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from . import biomes
from . import calibration
from . import config_migrations
from .config_merchant import MerchantConfigMixin
from .config_calib import CalibConfigMixin
from .config_autopop import AutopopConfigMixin
from .config_fishing import FishingConfigMixin
from .config_cycle import CycleConfigMixin
from .secure_store import SecureStore
from .time_tracking import default_tracking as _default_time_tracking, TIME_MODULES as _TIME_MODULES

if TYPE_CHECKING:
    from .config_types import Automation, AppSettings, BackendState

APP_VERSION = "1.0.0"
STABLE_FOLDER = "SolRich"
DEV_FOLDER = "SolRich-dev"
CONFIG_FILENAME = "config.json"

_LEGACY_FOLDERS = {STABLE_FOLDER: "Biomerich", DEV_FOLDER: "Biomerich-dev"}

def is_dev_build() -> bool:
    if "--dev" in sys.argv:
        return True
    if os.getenv("SOLRICH_DEV") or os.getenv("BIOMERICH_DEV"):
        return True

    if getattr(sys, "frozen", False):
        exe = os.path.basename(sys.executable).lower()
        if "dev" in exe:
            return True
    return False

APP_FOLDER = DEV_FOLDER if is_dev_build() else STABLE_FOLDER

def _base_dir() -> Path:
    base = os.getenv("LOCALAPPDATA")
    if not base:
        if sys.platform == "darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.getenv("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return Path(base)

def get_config_dir(folder: str = None) -> Path:
    resolved = folder or (DEV_FOLDER if is_dev_build() else STABLE_FOLDER)
    path = _base_dir() / resolved
    if not path.exists():
        legacy = _LEGACY_FOLDERS.get(resolved)
        if legacy:
            legacy_path = _base_dir() / legacy
            if legacy_path.is_dir():
                try:
                    shutil.copytree(legacy_path, path)
                except Exception:
                    pass
    path.mkdir(parents=True, exist_ok=True)
    return path

def _default_automation() -> "Automation":
    return {
        "mode": "idle",
        "biomeRandomizer": False,
        "strangeController": False,
        "merchantTeleporter": False,
        "preset": "",
        "amount": "1",
        "ocrFailsafe": {
            "strangeController": False,
            "biomeRandomizer": False,
            "merchantTeleporter": False,
            "fishing": False,
        },
        "notifications": {
            "strangeController": False,
            "biomeRandomizer": False,
            "merchantTeleporter": False,
            "merchantScreenshot": False,
            "merchantAutoBuy": False,
            "failsafes": False,
        },
        "pixels": {
            "inventory_button": None,
            "item_tab": None,
            "search_bar": None,
            "first_item_slot": None,
            "amount_box": None,
            "use_button": None,
        },
        "firstItemRegion": None,

        "biomePings": {},
        "autopop": {
            "biomes": {},
            "accounts": {},
            "ocrFailsafe": False,
            "amountRegion": None,
            "notifyUse": False,
            "notifyFail": False,
            "presets": {},
            "activePreset": "",
            "leaveLimboOnRareBiome": False,
        },
        "intervals": {
            "strangeController": 21 * 60,
            "biomeRandomizer": 36 * 60,
            "merchantTeleporter": 30 * 60,
        },
        "searchTerms": {
            "strangeController": "Strange Controller",
            "biomeRandomizer": "Biome Randomizer",
            "merchantTeleporter": "Merchant Teleporter",
        },
        "eden": {
            "account": None,
            "edenWatch": False,
            "edenInterval": 120,
        },
        "fishing": {
            "enabled": False,
            "preset": "",
            "account": None,
            "schedule": [],
            "webhookEnabled": False,
            "accounts": {},
            "pixels": {
                "cast_point": None,
                "bite_indicator": None,
                "bar_sample": None,
                "zone_left": None,
                "zone_right": None,
                "reel_click": None,
                "claim_button": None,
                "collection_button": None,
                "collection_close_button": None,
                "fish_dialogue": None,
                "sell_fish_button": None,
                "first_fish_slot": None,
                "sell_all_button": None,
                "sell_confirm_button": None,
                "fish_shop_close_button": None,
            },
        },
    }

def _default_config() -> dict:
    return {
        "version": APP_VERSION,
        "accounts": [],
        "webhooks": [],
        "biomeCounts": biomes.empty_counts(),
        "unknownBiomes": {},
        "merchantCounts": {"mari": 0, "jester": 0, "rin": 0},
        "moduleCounts": {"strangeController": 0, "biomeRandomizer": 0},
        "edenStats": {"count": 0, "lastFound": "", "log": [], "accountSeconds": {}},
        "settings": {
            "accentIndex": 0,
            "themeAnim": "none",
            "biomeLogging": True,
            "firstStartDone": False,
            "macroMode": "normal",
            "normalAccountId": None,
            "tokenConsent": False,
            "agreementAccepted": False,
            "tutorialVersion": "",
            "tesseractPromptDismissed": False,
            "streakCount": 0,
            "streakLastDate": "",
            "themeId": "none",
            "creatorNotes": "fortnite",
            "antiAfkEnabled": True,
            "antiAfkAction": "space",
            "antiAfkInterval": 300,
            "antiAfkStandalone": False,
            "ramTrimEnabled": False,
            "ramTrimInterval": 60,
            "throttleEnabled": False,
            "throttleMethod": "efficiency",
            "throttleCycleMs": 50,
            "throttleQuota": 12,
            "throttleFocusAware": True,
            "throttleOnlyWhenRunning": False,
            "throttleScope": "onlyThese",
            "throttleBreathe": True,
            "throttleRamCap": False,
            "throttleRamCapMb": 400,
            "throttleCollapsed": False,
            "throttleAccounts": [],
            "slowReset": False,
            "fakePingGuard": True,
            "hotkey": "F5",
        },
        "automation": _default_automation(),
        "timeTracking": _default_time_tracking(),
    }

class ConfigManager(MerchantConfigMixin, CalibConfigMixin, AutopopConfigMixin,
                    FishingConfigMixin, CycleConfigMixin):
    def __init__(self):
        self.dir = get_config_dir()
        self.path = self.dir / CONFIG_FILENAME
        self._lock = threading.RLock()
        self.tokens = SecureStore(self.dir)
        self._needs_save = False
        self._dirty = False
        self._save_stop = threading.Event()
        self._save_thread = None
        self.data = self._load()
        if self._needs_save:
            self.save_now()

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
                for k, v in (saved.get("merchantCounts") or {}).items():
                    if k in cfg["merchantCounts"] and isinstance(v, (int, float)):
                        cfg["merchantCounts"][k] = int(v)
                for k, v in (saved.get("moduleCounts") or {}).items():
                    if k in cfg["moduleCounts"] and isinstance(v, (int, float)):
                        cfg["moduleCounts"][k] = int(v)

                saved_eden = saved.get("edenStats")
                if isinstance(saved_eden, dict):
                    es = cfg["edenStats"]
                    if isinstance(saved_eden.get("count"), (int, float)):
                        es["count"] = int(saved_eden["count"])
                    if isinstance(saved_eden.get("lastFound"), str):
                        es["lastFound"] = saved_eden["lastFound"]
                    if isinstance(saved_eden.get("log"), list):
                        es["log"] = [str(x) for x in saved_eden["log"]][-50:]
                    if isinstance(saved_eden.get("accountSeconds"), dict):
                        secs = {}
                        for k, v in saved_eden["accountSeconds"].items():
                            try:
                                secs[str(k)] = float(v)
                            except (TypeError, ValueError):
                                pass
                        es["accountSeconds"] = secs

                saved_tt = saved.get("timeTracking")
                if isinstance(saved_tt, dict):
                    tt = cfg["timeTracking"]
                    for k, v in saved_tt.items():
                        if k == "modules" and isinstance(v, dict):
                            tt["modules"].update({mk: mv for mk, mv in v.items()})
                        else:
                            tt[k] = v
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Config] Could not read config.json ({e}) - using defaults.")

        for acc in cfg["accounts"]:
            acc["enabled"] = bool(acc.get("enabled", True))
            mods = acc.get("modules")
            if not isinstance(mods, dict):
                mods = {}
            acc["modules"] = {
                "strangeController": bool(mods.get("strangeController", False)),
                "biomeRandomizer": bool(mods.get("biomeRandomizer", False)),
                "merchantTeleporter": bool(mods.get("merchantTeleporter", False)),
                "fishing": bool(mods.get("fishing", False)),
            }
            legacy_token = acc.pop("token", None)
            if legacy_token and str(legacy_token).strip():
                self.tokens.set(acc.get("id"), str(legacy_token).strip())
                self._needs_save = True
        cfg["automation"].setdefault("fishing", {}).setdefault("account", None)
        eden = cfg["automation"].setdefault("eden", {})
        eden.setdefault("account", None)
        eden.setdefault("edenWatch", False)
        eden.setdefault("edenInterval", 120)
        if config_migrations.migrate_fishing(cfg):
            self._needs_save = True
        if config_migrations.migrate_cycle(cfg):
            self._needs_save = True
        notif = cfg["automation"].setdefault("notifications", {})
        for _k in ("strangeController", "biomeRandomizer", "merchantTeleporter",
                   "merchantScreenshot", "merchantAutoBuy", "failsafes"):
            notif.setdefault(_k, False)
        ap = cfg["automation"].setdefault("autopop", {})
        for _k, _v in (("accounts", {}), ("ocrFailsafe", False),
                       ("amountRegion", None), ("notifyUse", False),
                       ("notifyFail", False), ("presets", {}), ("activePreset", "")):
            ap.setdefault(_k, _v)
        if config_migrations.migrate_autopop(cfg, ap):
            self._needs_save = True
        if config_migrations.migrate_unknown_biomes(cfg):
            self._needs_save = True

        cfg["settings"]["biomeLogging"] = True
        self._sync_automation_flags(cfg)
        return cfg

    @staticmethod
    def _default_fishing_entry() -> dict:
        return config_migrations.default_fishing_entry()

    def _sync_automation_flags(self, cfg=None) -> None:
        data = cfg if cfg is not None else self.data
        accs = data.get("accounts", [])
        active = [a for a in accs if a.get("enabled", True)]
        auto = data.setdefault("automation", {})
        for task in ("strangeController", "biomeRandomizer", "merchantTeleporter"):
            auto[task] = any((a.get("modules") or {}).get(task) for a in active)
        fishing = auto.setdefault("fishing", {})
        fishing["moduleEnabled"] = any((a.get("modules") or {}).get("fishing") for a in active)
        all_ids = {a.get("id") for a in accs}
        active_ids = {a.get("id") for a in active}
        sched = fishing.get("schedule")
        if isinstance(sched, list):
            sched[:] = [e for e in sched
                        if isinstance(e, dict) and e.get("accId") in all_ids]
            fishing["enabled"] = any(e.get("accId") in active_ids for e in sched)
        else:
            fishing["schedule"] = []
            fishing["enabled"] = False
        if fishing.get("account") is not None and fishing["account"] not in all_ids:
            fishing["account"] = None
        eden = auto.get("eden")
        if isinstance(eden, dict) and eden.get("account") is not None and eden["account"] not in active_ids:
            eden["account"] = None
        cycle = auto.get("cycle")
        if isinstance(cycle, dict):
            steps = cycle.get("steps")
            if isinstance(steps, list):
                steps[:] = [s for s in steps
                            if isinstance(s, dict) and s.get("accId") in all_ids]
            limbo = cycle.get("limbo")
            if isinstance(limbo, dict) and isinstance(limbo.get("accounts"), dict):
                lacc = limbo["accounts"]
                for sid in list(lacc.keys()):
                    try:
                        keep = int(sid) in all_ids
                    except (TypeError, ValueError):
                        keep = False
                    if not keep:
                        del lacc[sid]

    def save(self) -> None:
        
        with self._lock:
            self._dirty = True
        self._ensure_flusher()

    def save_now(self) -> None:
        
        self._write_now()

    def _write_now(self) -> None:
        with self._lock:
            try:
                fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self.path)
                self._dirty = False
            except OSError as e:
                print(f"[Config] Saving failed: {e}")

    def _ensure_flusher(self) -> None:
        t = self._save_thread
        if t is not None and t.is_alive():
            return
        with self._lock:
            if self._save_thread is not None and self._save_thread.is_alive():
                return
            self._save_stop.clear()
            self._save_thread = threading.Thread(
                target=self._flush_loop, name="config-flusher", daemon=True)
            self._save_thread.start()

    def _flush_loop(self) -> None:
        while not self._save_stop.is_set():
            self._save_stop.wait(1.0)
            if self._dirty:
                self._write_now()

    @property
    def accounts(self) -> list:
        return self.data["accounts"]

    def enabled_accounts(self) -> list:
        
        accs = self.data["accounts"]
        s = self.data.get("settings", {}) or {}
        if s.get("macroMode") == "normal":
            nid = s.get("normalAccountId")
            only = [a for a in accs if a.get("id") == nid]
            if only:
                return only
            return accs[:1]
        return [a for a in accs if a.get("enabled", True)]

    def is_account_enabled(self, acc_id) -> bool:
        acc = self._find(self.data["accounts"], acc_id)
        return bool(acc and acc.get("enabled", True))

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
    def merchant_counts(self) -> dict:
        mc = self.data.setdefault("merchantCounts", {"mari": 0, "jester": 0, "rin": 0})
        for k in ("mari", "jester", "rin"):
            mc.setdefault(k, 0)
        return mc

    @property
    def module_counts(self) -> dict:
        mc = self.data.setdefault("moduleCounts", {"strangeController": 0, "biomeRandomizer": 0})
        for k in ("strangeController", "biomeRandomizer"):
            mc.setdefault(k, 0)
        return mc

    @property
    def eden_stats(self) -> dict:
        es = self.data.setdefault("edenStats", {"count": 0, "lastFound": "", "log": [], "accountSeconds": {}})
        es.setdefault("count", 0)
        es.setdefault("lastFound", "")
        es.setdefault("log", [])
        if not isinstance(es.get("accountSeconds"), dict):
            es["accountSeconds"] = {}
        return es

    @property
    def settings(self) -> "AppSettings":
        return self.data["settings"]

    @property
    def automation(self) -> "Automation":
        return self.data.setdefault("automation", _default_automation())

    def time_tracking(self) -> dict:
        tt = self.data.setdefault("timeTracking", _default_time_tracking())
        for k in ("totalEngine", "idle", "automation", "longestSession"):
            tt.setdefault(k, 0.0)
        tt.setdefault("sessions", 0)
        tt.setdefault("firstStart", "")
        tt.setdefault("lastStart", "")
        tt.setdefault("fishCaught", 0)
        mods = tt.setdefault("modules", {})
        for m in _TIME_MODULES:
            mods.setdefault(m, 0.0)
        return tt

    def reset_time_tracking(self) -> None:
        with self._lock:
            self.data["timeTracking"] = _default_time_tracking()
            self.save()

    def add_fish_caught(self, n: int = 1) -> int:
        
        with self._lock:
            tt = self.data.setdefault("timeTracking", _default_time_tracking())
            tt["fishCaught"] = int(tt.get("fishCaught", 0)) + int(n)
            total = tt["fishCaught"]
            self.save()
            return total

    def _safe_account(self, a: dict) -> dict:
        out = dict(a)
        out.pop("token", None)
        out["hasToken"] = self.tokens.has(a.get("id"))
        out["tokenUser"] = a.get("tokenUser", "")
        out["tokenValid"] = bool(a.get("tokenValid", False))
        return out

    def state(self) -> "BackendState":
        with self._lock:
            return {
                "version": self.data.get("version", "?"),
                "accounts": [self._safe_account(a) for a in self.accounts],
                "webhooks": [dict(w) for w in self.webhooks],
                "biomeCounts": dict(self.biome_counts),
                "moduleCounts": dict(self.module_counts),
                "unknownBiomes": dict(self.unknown_biomes),
                "merchantCounts": dict(self.merchant_counts),
                "edenStats": dict(self.eden_stats),
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
                "enabled": True,
                "modules": {"strangeController": False, "biomeRandomizer": False},
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

    def move_account(self, acc_id, direction: str) -> bool:
        
        with self._lock:
            accs = self.accounts
            idx = next((i for i, a in enumerate(accs) if a.get("id") == acc_id), -1)
            if idx < 0:
                return False
            j = idx + (1 if direction == "down" else -1)
            if j < 0 or j >= len(accs):
                return False
            accs[idx], accs[j] = accs[j], accs[idx]
            self.save()
            return True

    def delete_account(self, acc_id) -> bool:
        with self._lock:
            before = len(self.accounts)
            self.tokens.delete(acc_id)
            self.data["accounts"] = [a for a in self.accounts if a.get("id") != acc_id]
            for w in self.webhooks:
                w["routedAccounts"] = [i for i in w.get("routedAccounts", []) if i != acc_id]
            self._sync_automation_flags()
            self.save()
            return len(self.accounts) != before

    def set_account_enabled(self, acc_id, enabled: bool) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            acc["enabled"] = bool(enabled)
            if not enabled:
                from . import win_windows
                win_windows.clear_manual_bind(acc_id)
            self._sync_automation_flags()
            self.save()
            return True

    def set_account_module(self, acc_id, task: str, enabled: bool) -> bool:
        if task not in ("strangeController", "biomeRandomizer", "merchantTeleporter", "auraDetection", "fishing"):
            return False
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            mods = acc.setdefault("modules", {"strangeController": False, "biomeRandomizer": False})
            mods[task] = bool(enabled)
            if task == "fishing" and enabled:
                for other in self.accounts:
                    if other is not acc:
                        other.setdefault("modules", {})["fishing"] = False
            self._sync_automation_flags()
            self.save()
            return True

    def set_fishing_account(self, acc_id) -> bool:
        with self._lock:
            if acc_id is not None and not self._find(self.accounts, acc_id):
                return False
            fishing = self.automation.setdefault("fishing", {})
            fishing["account"] = acc_id
            self._sync_automation_flags()
            self.save()
            return True

    def fishing_schedule(self) -> list:
        sched = self._fishing().get("schedule")
        return sched if isinstance(sched, list) else []

    def set_fishing_schedule(self, schedule) -> bool:
        
        with self._lock:
            valid = {a.get("id") for a in self.accounts}
            clean, seen = [], set()
            for e in (schedule or []):
                if not isinstance(e, dict):
                    continue
                aid = e.get("accId")
                if aid not in valid or aid in seen:
                    continue
                try:
                    mins = max(1, min(1440, int(e.get("minutes", 30))))
                except (TypeError, ValueError):
                    mins = 30
                seen.add(aid)
                clean.append({"accId": aid, "minutes": mins})
            self._fishing()["schedule"] = clean
            self._sync_automation_flags()
            self.save()
            return True

    def set_account_token(self, acc_id, token: str) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            self.tokens.set(acc_id, (token or "").strip())
            acc.pop("token", None)
            acc["tokenUser"] = ""
            acc["tokenValid"] = False
            self.save()
            return True

    def set_account_token_status(self, acc_id, user: str, valid: bool) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            acc["tokenUser"] = user or ""
            acc["tokenValid"] = bool(valid)
            self.save()
            return True

    def clear_account_token(self, acc_id) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            self.tokens.delete(acc_id)
            acc.pop("token", None)
            acc["tokenUser"] = ""
            acc["tokenValid"] = False
            self.save()
            return True

    def account_token(self, acc_id) -> str:
        with self._lock:
            return self.tokens.get(acc_id)

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

    def reset_to_defaults(self) -> None:
        
        with self._lock:
            self.data = _default_config()
            try:
                if hasattr(self.tokens, "clear"):
                    self.tokens.clear()
            except Exception:
                pass
            self.save_now()

    def _snapshot_calibration(self) -> dict:
        
        auto = self.automation
        cp = lambda v: json.loads(json.dumps(v)) if v is not None else None
        fishing = auto.get("fishing") or {}
        merch = auto.get("merchants") or {}
        autopop = auto.get("autopop") or {}
        return {
            "pixels": cp(auto.get("pixels")),
            "firstItemRegion": cp(auto.get("firstItemRegion")),
            "calib": cp(auto.get("calib")),
            "fishing_pixels": cp(fishing.get("pixels")),
            "fishing_regions": cp(fishing.get("regions")),
            "fishing_firstItemRegion": cp(fishing.get("firstItemRegion")),
            "merchants_calib": cp(merch.get("calib")),
            "autopop_amountRegion": cp(autopop.get("amountRegion")),
        }

    def _restore_calibration(self, snap: dict) -> None:
        auto = self.automation
        if snap.get("pixels") is not None: auto["pixels"] = snap["pixels"]
        if snap.get("firstItemRegion") is not None: auto["firstItemRegion"] = snap["firstItemRegion"]
        if snap.get("calib") is not None: auto["calib"] = snap["calib"]
        if snap.get("merchants_calib") is not None:
            auto.setdefault("merchants", {})["calib"] = snap["merchants_calib"]
        fishing = auto.setdefault("fishing", {})
        if snap.get("fishing_pixels") is not None: fishing["pixels"] = snap["fishing_pixels"]
        if snap.get("fishing_regions") is not None: fishing["regions"] = snap["fishing_regions"]
        if snap.get("fishing_firstItemRegion") is not None: fishing["firstItemRegion"] = snap["fishing_firstItemRegion"]
        if snap.get("autopop_amountRegion") is not None:
            auto.setdefault("autopop", {})["amountRegion"] = snap["autopop_amountRegion"]

    def force_reset_once(self, token: str) -> bool:
        
        with self._lock:
            if self.settings.get("forcedResetToken") == token:
                return False
            calib = self._snapshot_calibration()
            self.reset_to_defaults()
            self._restore_calibration(calib)
            self.settings["forcedResetToken"] = token
            self.save_now()
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
        if task not in ("strangeController", "biomeRandomizer", "merchantTeleporter"):
            return
        with self._lock:
            self.automation[task] = bool(enabled)
            self.save()

    def set_search_term(self, task: str, term: str) -> None:
        if task not in ("strangeController", "biomeRandomizer", "merchantTeleporter"):
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


            regions = presets.get_preset_regions(name)
            fir = regions.get("first_item_region")
            if fir:
                self.automation["firstItemRegion"] = list(fir)
                pixels["first_item_slot"] = calibration.region_center(fir)
            apr = regions.get("autopop_amount_region")
            if apr:
                self.automation.setdefault("autopop", {})["amountRegion"] = list(apr)
            self.automation["preset"] = name
            self.save()
            return True

    def set_ocr_failsafe(self, task: str, enabled: bool) -> None:
        allowed = ("strangeController", "biomeRandomizer", "merchantTeleporter", "fishing",
                   "fishingFailed", "sellFishShop", "noBite")
        if task not in allowed:
            return
        with self._lock:
            v = self.automation.setdefault("ocrFailsafe", {})
            if not isinstance(v, dict):
                v = {}
                self.automation["ocrFailsafe"] = v
            v[task] = bool(enabled)
            self.save()

    def set_notification(self, key: str, enabled: bool) -> None:
        allowed = ("strangeController", "biomeRandomizer", "merchantTeleporter",
                   "merchantScreenshot", "merchantAutoBuy", "failsafes")
        if key not in allowed:
            return
        with self._lock:
            v = self.automation.setdefault("notifications", {})
            if not isinstance(v, dict):
                v = {}
                self.automation["notifications"] = v
            v[key] = bool(enabled)
            self.save()


    def _biome_pings(self) -> dict:
        bp = self.automation.get("biomePings")
        if not isinstance(bp, dict):
            bp = {}
            self.automation["biomePings"] = bp
        return bp

    def set_biome_ping(self, biome_key: str, ptype: str, pid) -> dict:
        
        with self._lock:
            bp = self._biome_pings()
            if ptype not in ("user", "role", "everyone"):
                ptype = "user"
            digits = "".join(c for c in str(pid or "") if c.isdigit())
            bp[biome_key] = {"type": ptype, "id": digits}
            self.save()
            return dict(bp)

    def biome_ping_content(self, biome_key: str):
        
        if biome_key in biomes.PING_BIOMES:
            return "@everyone"
        cfg = self._biome_pings().get(biome_key)
        if not isinstance(cfg, dict):
            return None
        ptype = cfg.get("type")
        pid = "".join(c for c in str(cfg.get("id") or "") if c.isdigit())
        if ptype == "everyone":
            return "@everyone"
        if ptype == "user" and pid:
            return f"<@{pid}>"
        if ptype == "role" and pid:
            return f"<@&{pid}>"
        return ""

    def set_streak_count(self, value) -> int:
        with self._lock:
            settings = self.data.setdefault("settings", {})
            from datetime import date
            count = max(0, int(value))
            settings["streakCount"] = count
            settings["streakLastDate"] = date.today().isoformat()
            self.save()
            return count

    def touch_streak(self) -> dict:
        with self._lock:
            settings = self.data.setdefault("settings", {})
            today = date.today()
            today_str = today.isoformat()
            last_str = settings.get("streakLastDate", "")
            previous = int(settings.get("streakCount", 0) or 0)

            if last_str == today_str:
                count = previous
                advanced = False
            else:
                try:
                    last = date.fromisoformat(last_str) if last_str else None
                except ValueError:
                    last = None
                if last is not None and last == today - timedelta(days=1):
                    count = previous + 1
                else:
                    count = 1
                advanced = True
                settings["streakCount"] = count
                settings["streakLastDate"] = today_str
                self.save()

            return {"count": count, "previous": previous, "advanced": advanced}

    def reset_biome_counts(self) -> None:
        with self._lock:
            for k in list(self.biome_counts.keys()):
                self.biome_counts[k] = 0
            self.data["unknownBiomes"] = {}
            self.save()

    def increment_biome(self, key: str) -> None:
        with self._lock:
            if key in self.biome_counts:
                self.biome_counts[key] += 1
                self.save()

    def increment_module_use(self, task: str) -> int:
        
        with self._lock:
            mc = self.module_counts
            if task not in mc:
                return 0
            mc[task] = int(mc.get(task, 0)) + 1
            total = mc[task]
            self.save()
            return total

    def increment_merchant(self, mid: str) -> int:
        
        mid = (mid or "").strip().lower()
        with self._lock:
            mc = self.merchant_counts
            if mid not in mc:
                return 0
            mc[mid] = int(mc.get(mid, 0)) + 1
            total = mc[mid]
            self.save()
            return total

    def reset_merchant_counts(self) -> None:
        with self._lock:
            for k in ("mari", "jester", "rin"):
                self.merchant_counts[k] = 0
            self.save()

    def increment_eden(self) -> dict:
        
        from datetime import datetime, timezone
        with self._lock:
            es = self.eden_stats
            es["count"] = int(es.get("count", 0)) + 1
            ts = datetime.now(timezone.utc).isoformat()
            es["lastFound"] = ts
            log = es.setdefault("log", [])
            log.append(ts)
            del log[:-50]
            self.save()
            return {"count": es["count"], "lastFound": es["lastFound"], "log": list(es["log"])}

    def add_eden_time(self, acc_id, seconds: float) -> None:
        
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return
        if seconds <= 0:
            return
        with self._lock:
            secs = self.eden_stats.setdefault("accountSeconds", {})
            sid = str(acc_id)
            secs[sid] = float(secs.get(sid, 0.0)) + seconds
            self.save()

    def reset_eden_stats(self) -> None:
        with self._lock:
            self.data["edenStats"] = {"count": 0, "lastFound": "", "log": [], "accountSeconds": {}}
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
