import json
import math
import os
import shutil
import sys
import tempfile
import threading
from datetime import date, datetime, timedelta
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
from .secure_store import SecureStore, SecureStoreError
from .time_tracking import (
    default_tracking as _default_time_tracking,
    TIME_MODULES as _TIME_MODULES,
)

if TYPE_CHECKING:
    from .config_types import Automation, AppSettings, BackendState

APP_VERSION = "1.2.1"
STABLE_FOLDER = "SolRich"
DEV_FOLDER = "SolRich-dev"
CONFIG_FILENAME = "config.json"
CONFIG_BACKUP_FILENAME = "config.json.bak"

CYBERSPACE_ODDS = 5000
MODULE_USE_TASKS = ("strangeController", "biomeRandomizer")

_LEGACY_FOLDERS = {STABLE_FOLDER: "Biomerich", DEV_FOLDER: "Biomerich-dev"}


def _default_module_use_stats() -> dict:
    
    return {
        "accounts": {},
        "cyberspaceBaseline": {task: 0 for task in MODULE_USE_TASKS},
        "lastCyberspace": "",
        "lastCyberspaceUnix": 0.0,
        "lastCyberspaceAccount": None,
        "trackingSince": "",
        "anchorReason": "trackingStart",
        "accurateSinceLastCyberspace": True,
    }


def _nonnegative_int(value, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return max(0, int(default))


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
    legacy = _LEGACY_FOLDERS.get(resolved)
    if legacy:
        legacy_path = _base_dir() / legacy
        if legacy_path.is_dir():
            try:
                if not path.exists():
                    shutil.copytree(legacy_path, path)
                elif (
                    not (path / CONFIG_FILENAME).exists()
                    and (legacy_path / CONFIG_FILENAME).is_file()
                ):



                    path.mkdir(parents=True, exist_ok=True)
                    for filename in (
                        CONFIG_FILENAME,
                        CONFIG_BACKUP_FILENAME,
                        "tokens.dat",
                    ):
                        source = legacy_path / filename
                        target = path / filename
                        if source.is_file() and not target.exists():
                            shutil.copy2(source, target)
                    print(
                        f"[Config] Recovered user data from legacy folder '{legacy}'."
                    )
            except Exception as exc:
                print(f"[Config] Legacy migration failed: {exc}")
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
        "moduleUseStats": _default_module_use_stats(),
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
            "customThemeBackgroundFile": "",
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
            "safeCpuLimiterV2": True,
            "throttleCollapsed": False,
            "throttleAccounts": [],
            "performanceBenchmarks": [],
            "slowReset": False,
            "fakePingGuard": True,
            "fakePingPrompt": True,
            "monitorDimEnabled": False,
            "monitorDimLevel": 40,
            "windowsNotificationsEnabled": True,
            "windowsNotifyBiomes": False,
            "windowsNotifyDisconnects": True,
            "windowsNotifyAuras": False,
            "windowsNotifyBiomeHealth": True,
            "windowsAuraMinimumRarity": "1000000",
            "biomeHealthMonitorEnabled": True,
            "biomeHealthTimeoutMinutes": 30,
            "auraPushNotify": False,
            "auraMinimumRarity": "",
            "auraAlwaysSendNames": "",
            "auraPingUserId": "",
            "auraPingMinimumRarity": "",
            "auraAlwaysPingNames": "",
            "clippingEnabled": False,
            "clipHotkey": "F8",
            "clipBiomes": ["glitched", "dreamspace", "cyberspace", "singularity"],
            "clipBiomeDelay": "60",
            "clipAuraMinimumRarity": "99999999",
            "clipAuraNames": "Illusionary",
            "clipAuraDelay": "60",
            "hotkey": "F5",
        },
        "automation": _default_automation(),
        "timeTracking": _default_time_tracking(),
    }


class ConfigManager(
    MerchantConfigMixin,
    CalibConfigMixin,
    AutopopConfigMixin,
    FishingConfigMixin,
    CycleConfigMixin,
):
    def __init__(self):
        self.dir = get_config_dir()
        self.path = self.dir / CONFIG_FILENAME
        self.backup_path = self.dir / CONFIG_BACKUP_FILENAME
        self._lock = threading.RLock()
        self.tokens = SecureStore(self.dir)
        self._needs_save = False
        self._dirty = False
        self._save_stop = threading.Event()
        self._save_thread = None
        self.recovery_notice = None
        self.recovery_file = None
        self._unrecoverable_load_error = False
        self.data = self._load()
        self.reset_module_session_stats()
        if self._needs_save and not self._unrecoverable_load_error:
            self.save_now()

    @staticmethod
    def _validate_saved_config(saved) -> dict:
        if not isinstance(saved, dict) or not saved:
            raise ValueError("config root is empty or not an object")
        if not any(
            key in saved for key in ("accounts", "webhooks", "settings", "automation")
        ):
            raise ValueError("config has no recognized data sections")

        expected_dicts = (
            "settings",
            "automation",
            "biomeCounts",
            "unknownBiomes",
            "merchantCounts",
            "moduleCounts",
            "moduleUseStats",
            "edenStats",
            "timeTracking",
        )
        for key in expected_dicts:
            if key in saved and not isinstance(saved[key], dict):
                raise ValueError(f"config section '{key}' is not an object")
        for key in ("accounts", "webhooks"):
            if key in saved and not isinstance(saved[key], list):
                raise ValueError(f"config section '{key}' is not a list")
            if key in saved and any(not isinstance(item, dict) for item in saved[key]):
                raise ValueError(f"config section '{key}' contains an invalid entry")
        return saved

    @classmethod
    def _read_config_file(cls, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as stream:
            return cls._validate_saved_config(json.load(stream))

    @staticmethod
    def _atomic_replace_bytes(path: Path, payload: bytes) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass

    def _refresh_backup_from(self, source: Path) -> None:
        saved = self._read_config_file(source)
        payload = json.dumps(saved, indent=2, ensure_ascii=False).encode("utf-8")
        self._atomic_replace_bytes(self.backup_path, payload)

    def _quarantine_bad_config(self) -> None:
        if not self.path.exists():
            return
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        target = self.dir / f"config.corrupt.{stamp}.json"
        suffix = 1
        while target.exists():
            target = self.dir / f"config.corrupt.{stamp}.{suffix}.json"
            suffix += 1
        try:
            shutil.copy2(self.path, target)
            self.recovery_file = target.name
            copies = sorted(
                self.dir.glob("config.corrupt.*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            for old in copies[3:]:
                try:
                    old.unlink()
                except OSError:
                    pass
            print(f"[Config] Preserved unreadable config as '{target.name}'.")
        except OSError as exc:
            print(f"[Config] Could not preserve unreadable config: {exc}")

    def _load_saved_config(self):
        primary_error = None
        if self.path.exists():
            try:
                saved = self._read_config_file(self.path)
                try:
                    self._refresh_backup_from(self.path)
                except OSError as exc:
                    print(f"[Config] Could not refresh backup: {exc}")
                return saved
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                primary_error = exc
                print(f"[Config] Primary config is unreadable ({exc}).")
                self._quarantine_bad_config()

        if self.backup_path.exists():
            try:
                saved = self._read_config_file(self.backup_path)
                self.recovery_notice = "backup"
                self._needs_save = True
                print("[Config] Restored user data from config.json.bak.")
                return saved
            except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
                print(f"[Config] Backup config is unreadable ({exc}).")

        if primary_error is not None:
            self.recovery_notice = "unrecoverable"
            self._unrecoverable_load_error = True
            print(
                "[Config] No valid backup found; using defaults without deleting the quarantined file."
            )
        return None

    def _load(self) -> dict:
        cfg = _default_config()
        migrate_legacy_cpu_limiter = False
        saved = self._load_saved_config()
        if saved is not None:
            try:
                saved_settings = saved.get("settings")
                migrate_legacy_cpu_limiter = (
                    isinstance(saved_settings, dict)
                    and saved_settings.get("safeCpuLimiterV2") is not True
                )
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

                saved_module_stats = saved.get("moduleUseStats")
                if isinstance(saved_module_stats, dict):
                    stats = _default_module_use_stats()
                    saved_accounts = saved_module_stats.get("accounts")
                    if isinstance(saved_accounts, dict):
                        for acc_id, values in saved_accounts.items():
                            if not isinstance(values, dict):
                                continue
                            stats["accounts"][str(acc_id)] = {
                                task: _nonnegative_int(values.get(task, 0))
                                for task in MODULE_USE_TASKS
                            }
                    saved_baseline = saved_module_stats.get("cyberspaceBaseline")
                    if isinstance(saved_baseline, dict):
                        stats["cyberspaceBaseline"] = {
                            task: _nonnegative_int(saved_baseline.get(task, 0))
                            for task in MODULE_USE_TASKS
                        }
                    for key in ("lastCyberspace", "trackingSince"):
                        if isinstance(saved_module_stats.get(key), str):
                            stats[key] = saved_module_stats[key]
                    try:
                        stats["lastCyberspaceUnix"] = max(
                            0.0,
                            float(saved_module_stats.get("lastCyberspaceUnix", 0) or 0),
                        )
                    except (TypeError, ValueError, OverflowError):
                        stats["lastCyberspaceUnix"] = 0.0
                    stats["lastCyberspaceAccount"] = saved_module_stats.get(
                        "lastCyberspaceAccount"
                    )
                    anchor_reason = saved_module_stats.get("anchorReason")
                    if anchor_reason in (
                        "trackingStart",
                        "cyberspace",
                        "statsReset",
                        "migration",
                    ):
                        stats["anchorReason"] = anchor_reason
                    elif stats["lastCyberspace"]:
                        stats["anchorReason"] = "cyberspace"
                    stats["accurateSinceLastCyberspace"] = bool(
                        saved_module_stats.get("accurateSinceLastCyberspace", True)
                    )
                    cfg["moduleUseStats"] = stats
                elif int(cfg["biomeCounts"].get("cyberspace", 0) or 0) > 0:



                    cfg["moduleUseStats"]["cyberspaceBaseline"] = {
                        task: _nonnegative_int(cfg["moduleCounts"].get(task, 0))
                        for task in MODULE_USE_TASKS
                    }
                    from datetime import datetime, timezone

                    cfg["moduleUseStats"]["trackingSince"] = datetime.now(
                        timezone.utc
                    ).isoformat()
                    cfg["moduleUseStats"]["accurateSinceLastCyberspace"] = False
                    cfg["moduleUseStats"]["anchorReason"] = "migration"
                    self._needs_save = True

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
            except (AttributeError, TypeError, ValueError) as e:
                print(f"[Config] Could not merge config data ({e}) - using defaults.")
                cfg = _default_config()
                self.recovery_notice = "unrecoverable"
                self._unrecoverable_load_error = True

        settings = cfg["settings"]


        if not settings.get("auraMinimumRarity") and settings.get("auraSendRarity"):
            settings["auraMinimumRarity"] = settings.get("auraSendRarity")
            self._needs_save = True
        if not settings.get("auraAlwaysSendNames") and settings.get(
            "auraNoRarityNames"
        ):
            settings["auraAlwaysSendNames"] = settings.get("auraNoRarityNames")
            self._needs_save = True
        for legacy_aura_key in (
            "auraCheckInterval",
            "auraSendRarity",
            "auraNoRarityNames",
            "auraScreenshot",
        ):
            if legacy_aura_key in settings:
                settings.pop(legacy_aura_key, None)
                self._needs_save = True
        if migrate_legacy_cpu_limiter:




            was_legacy_suspend = settings.get("throttleMethod") == "suspend"
            if was_legacy_suspend and settings.get("throttleRamCap"):
                print(
                    "[Config] Disabled legacy hard RAM cap for the safe CPU limiter migration."
                )
            if was_legacy_suspend:
                settings["throttleMethod"] = "cpuLimit"
                settings["throttleRamCap"] = False
            settings["safeCpuLimiterV2"] = True
            self._needs_save = True

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
                "auraDetection": bool(mods.get("auraDetection", False)),
            }
            legacy_token = acc.get("token")
            if legacy_token and str(legacy_token).strip():
                try:
                    self.tokens.set(acc.get("id"), str(legacy_token).strip())
                    acc.pop("token", None)
                    self._needs_save = True
                except SecureStoreError as exc:


                    print(
                        f"[Config] Legacy token migration is waiting for secure storage: {exc}"
                    )
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
        for _k in (
            "strangeController",
            "biomeRandomizer",
            "merchantTeleporter",
            "merchantScreenshot",
            "merchantAutoBuy",
            "failsafes",
        ):
            notif.setdefault(_k, False)
        ap = cfg["automation"].setdefault("autopop", {})
        for _k, _v in (
            ("accounts", {}),
            ("ocrFailsafe", False),
            ("amountRegion", None),
            ("notifyUse", False),
            ("notifyFail", False),
            ("presets", {}),
            ("activePreset", ""),
        ):
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
        fishing["moduleEnabled"] = any(
            (a.get("modules") or {}).get("fishing") for a in active
        )
        all_ids = {a.get("id") for a in accs}
        active_ids = {a.get("id") for a in active}
        sched = fishing.get("schedule")
        if isinstance(sched, list):
            sched[:] = [
                e for e in sched if isinstance(e, dict) and e.get("accId") in all_ids
            ]
            fishing["enabled"] = any(e.get("accId") in active_ids for e in sched)
        else:
            fishing["schedule"] = []
            fishing["enabled"] = False
        if fishing.get("account") is not None and fishing["account"] not in all_ids:
            fishing["account"] = None
        eden = auto.get("eden")
        if (
            isinstance(eden, dict)
            and eden.get("account") is not None
            and eden["account"] not in active_ids
        ):
            eden["account"] = None
        cycle = auto.get("cycle")
        if isinstance(cycle, dict):
            steps = cycle.get("steps")
            if isinstance(steps, list):
                steps[:] = [
                    s
                    for s in steps
                    if isinstance(s, dict) and s.get("accId") in all_ids
                ]
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

    def save_on_shutdown(self) -> None:
        
        if self._unrecoverable_load_error and not self._dirty:
            print("[Config] Skipped shutdown save after unrecoverable load error.")
            return
        self._write_now()

    def _write_now(self) -> None:
        with self._lock:
            try:
                payload = json.dumps(self.data, indent=2, ensure_ascii=False).encode(
                    "utf-8"
                )
                if self.path.exists():
                    try:
                        self._refresh_backup_from(self.path)
                    except (
                        json.JSONDecodeError,
                        OSError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        print(
                            f"[Config] Kept existing backup; current file was not valid ({exc})."
                        )
                self._atomic_replace_bytes(self.path, payload)



                self._atomic_replace_bytes(self.backup_path, payload)
                self._dirty = False
                self._unrecoverable_load_error = False
            except (OSError, TypeError, ValueError) as e:
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
                target=self._flush_loop, name="config-flusher", daemon=True
            )
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

    def effective_eden_account_id(self):
        
        settings = self.data.get("settings", {}) or {}
        if settings.get("macroMode") == "normal":
            accounts = self.enabled_accounts()
            return accounts[0].get("id") if accounts else None
        eden = self.data.get("automation", {}).get("eden", {}) or {}
        return eden.get("account")

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
        mc = self.data.setdefault(
            "moduleCounts", {"strangeController": 0, "biomeRandomizer": 0}
        )
        for k in MODULE_USE_TASKS:
            mc.setdefault(k, 0)
        return mc

    @property
    def module_use_stats(self) -> dict:
        stats = self.data.setdefault("moduleUseStats", _default_module_use_stats())
        accounts = stats.setdefault("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
            stats["accounts"] = accounts
        baseline = stats.setdefault("cyberspaceBaseline", {})
        if not isinstance(baseline, dict):
            baseline = {}
            stats["cyberspaceBaseline"] = baseline
        for task in MODULE_USE_TASKS:
            baseline.setdefault(task, 0)
        stats.setdefault("lastCyberspace", "")
        stats.setdefault("lastCyberspaceUnix", 0.0)
        stats.setdefault("lastCyberspaceAccount", None)
        stats.setdefault("trackingSince", "")
        stats.setdefault("anchorReason", "trackingStart")
        stats.setdefault("accurateSinceLastCyberspace", True)
        return stats

    @property
    def eden_stats(self) -> dict:
        es = self.data.setdefault(
            "edenStats", {"count": 0, "lastFound": "", "log": [], "accountSeconds": {}}
        )
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


        out.pop("windowBinding", None)
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
                "cyberspaceProgress": self.cyberspace_progress(),
                "unknownBiomes": dict(self.unknown_biomes),
                "merchantCounts": dict(self.merchant_counts),
                "edenStats": dict(self.eden_stats),
                "settings": dict(self.settings),
                "automation": json.loads(json.dumps(self.automation)),
                "configRecovery": {
                    "status": self.recovery_notice,
                    "preservedFile": self.recovery_file,
                }
                if self.recovery_notice
                else None,
            }

    def _find(self, items, item_id):
        return next((x for x in items if x.get("id") == item_id), None)

    @staticmethod
    def _account_name_key(name) -> str:
        return str(name or "").strip().casefold()

    def account_name_owner(self, name, exclude_id=None):
        
        key = self._account_name_key(name)
        if not key:
            return None
        with self._lock:
            return next(
                (
                    acc
                    for acc in self.accounts
                    if acc.get("id") != exclude_id
                    and self._account_name_key(acc.get("name")) == key
                ),
                None,
            )

    def token_owner(self, token, exclude_id=None):
        
        wanted = str(token or "").strip()
        if not wanted:
            return None
        with self._lock:
            return next(
                (
                    acc
                    for acc in self.accounts
                    if acc.get("id") != exclude_id
                    and self.tokens.get(acc.get("id")) == wanted
                ),
                None,
            )

    def linked_user_owner(self, username, exclude_id=None):
        
        key = self._account_name_key(username)
        if not key:
            return None
        with self._lock:
            return next(
                (
                    acc
                    for acc in self.accounts
                    if acc.get("id") != exclude_id
                    and self.tokens.has(acc.get("id"))
                    and self._account_name_key(acc.get("tokenUser")) == key
                ),
                None,
            )

    def add_account(
        self,
        name: str,
        link: str = "",
        avatar: str = "",
        acc_id=None,
        roblox_user_id=None,
        roblox_username: str = "",
    ) -> dict:
        with self._lock:
            if self.account_name_owner(name):
                raise ValueError("duplicate_account")
            acc = {
                "id": acc_id or self._new_id(),
                "name": name.strip(),
                "link": (link or "").strip(),
                "avatar": avatar or "",
                "robloxUserId": roblox_user_id,
                "robloxUsername": roblox_username or "",
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
                if self.account_name_owner(name, exclude_id=acc_id):
                    raise ValueError("duplicate_account")
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
                w["routedAccounts"] = [
                    i for i in w.get("routedAccounts", []) if i != acc_id
                ]
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
        if task not in (
            "strangeController",
            "biomeRandomizer",
            "merchantTeleporter",
            "auraDetection",
            "fishing",
        ):
            return False
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            mods = acc.setdefault(
                "modules", {"strangeController": False, "biomeRandomizer": False}
            )
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
            for e in schedule or []:
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

    def set_account_token_status(
        self, acc_id, user: str, valid: bool, roblox_user_id=None
    ) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            acc["tokenUser"] = user or ""
            acc["tokenValid"] = bool(valid)
            if roblox_user_id is not None:
                acc["robloxUserId"] = roblox_user_id
                acc["robloxUsername"] = user or acc.get("robloxUsername", "")
            self.save()
            return True

    def set_account_profile(
        self, acc_id, user_id=None, username="", avatar=None
    ) -> bool:
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            if not acc:
                return False
            acc["robloxUserId"] = user_id
            acc["robloxUsername"] = username or ""
            if avatar is not None:
                acc["avatar"] = avatar or ""
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

    def clear_all_account_tokens(self) -> int:
        
        with self._lock:
            count = sum(
                1
                for acc in self.accounts
                if self.tokens.has(acc.get("id")) or str(acc.get("token") or "").strip()
            )
            self.tokens.clear()
            for acc in self.accounts:
                acc.pop("token", None)
                acc["tokenUser"] = ""
                acc["tokenValid"] = False
            self.save()
            return count

    def token_security_status(self) -> dict:
        with self._lock:
            status = self.tokens.status()
            plaintext_legacy = sum(
                1 for acc in self.accounts if str(acc.get("token") or "").strip()
            )
            status["legacyConfigTokens"] = plaintext_legacy
            if plaintext_legacy:
                status["storedTokens"] += plaintext_legacy
                status["status"] = "warning"
                status["encrypted"] = False
            return status

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
        if snap.get("pixels") is not None:
            auto["pixels"] = snap["pixels"]
        if snap.get("firstItemRegion") is not None:
            auto["firstItemRegion"] = snap["firstItemRegion"]
        if snap.get("calib") is not None:
            auto["calib"] = snap["calib"]
        if snap.get("merchants_calib") is not None:
            auto.setdefault("merchants", {})["calib"] = snap["merchants_calib"]
        fishing = auto.setdefault("fishing", {})
        if snap.get("fishing_pixels") is not None:
            fishing["pixels"] = snap["fishing_pixels"]
        if snap.get("fishing_regions") is not None:
            fishing["regions"] = snap["fishing_regions"]
        if snap.get("fishing_firstItemRegion") is not None:
            fishing["firstItemRegion"] = snap["fishing_firstItemRegion"]
        if snap.get("autopop_amountRegion") is not None:
            auto.setdefault("autopop", {})["amountRegion"] = snap[
                "autopop_amountRegion"
            ]

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
        allowed = (
            "strangeController",
            "biomeRandomizer",
            "merchantTeleporter",
            "fishing",
            "fishingFailed",
            "sellFishShop",
            "noBite",
        )
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
        allowed = (
            "strangeController",
            "biomeRandomizer",
            "merchantTeleporter",
            "merchantScreenshot",
            "merchantAutoBuy",
            "failsafes",
        )
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
            if ptype not in ("none", "user", "role", "everyone"):
                ptype = "none"
            digits = "".join(c for c in str(pid or "") if c.isdigit())
            if ptype in ("none", "everyone"):
                digits = ""
            bp[biome_key] = {"type": ptype, "id": digits}
            self.save()
            return dict(bp)

    def biome_ping_content(self, biome_key: str):
        
        cfg = self._biome_pings().get(biome_key)
        if not isinstance(cfg, dict):
            return "@everyone" if biome_key in biomes.PING_BIOMES else None
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



            stats = self.module_use_stats
            stats["cyberspaceBaseline"] = {
                task: _nonnegative_int(self.module_counts.get(task, 0))
                for task in MODULE_USE_TASKS
            }
            stats["lastCyberspace"] = ""
            stats["lastCyberspaceUnix"] = 0.0
            stats["lastCyberspaceAccount"] = None
            stats["accurateSinceLastCyberspace"] = True
            stats["anchorReason"] = "statsReset"
            self.save()

    def increment_biome(
        self, key: str, acc_id=None, *, track_progress: bool = True
    ) -> None:
        with self._lock:
            if key in self.biome_counts:
                self.biome_counts[key] += 1
                if key == "cyberspace" and track_progress:
                    from datetime import datetime, timezone
                    import time

                    stats = self.module_use_stats
                    stats["cyberspaceBaseline"] = {
                        task: _nonnegative_int(self.module_counts.get(task, 0))
                        for task in MODULE_USE_TASKS
                    }
                    stats["lastCyberspace"] = datetime.now(timezone.utc).isoformat()
                    stats["lastCyberspaceUnix"] = time.time()
                    stats["lastCyberspaceAccount"] = acc_id
                    stats["accurateSinceLastCyberspace"] = True
                    stats["anchorReason"] = "cyberspace"
                    self._session_cyberspaces = (
                        int(getattr(self, "_session_cyberspaces", 0)) + 1
                    )



                    self.save_now()
                else:
                    self.save()

    def increment_module_use(self, task: str, acc_id=None, used_at=None) -> int:
        
        with self._lock:
            mc = self.module_counts
            if task not in mc:
                return 0
            mc[task] = int(mc.get(task, 0)) + 1
            total = mc[task]





            try:
                clicked_before_last_cyberspace = used_at is not None and float(
                    self.module_use_stats.get("lastCyberspaceUnix", 0) or 0
                ) >= float(used_at)
            except (TypeError, ValueError, OverflowError):
                clicked_before_last_cyberspace = False
            if clicked_before_last_cyberspace:
                baseline = self.module_use_stats["cyberspaceBaseline"]
                baseline[task] = min(total, _nonnegative_int(baseline.get(task, 0)) + 1)

            if acc_id is not None:
                account_key = str(acc_id)
                account_stats = self.module_use_stats["accounts"].setdefault(
                    account_key, {name: 0 for name in MODULE_USE_TASKS}
                )
                account_stats[task] = int(account_stats.get(task, 0) or 0) + 1

                session_stats = self._session_module_counts.setdefault(
                    account_key, {name: 0 for name in MODULE_USE_TASKS}
                )
                session_stats[task] = int(session_stats.get(task, 0) or 0) + 1
            if not self.module_use_stats.get("trackingSince"):
                from datetime import datetime, timezone

                self.module_use_stats["trackingSince"] = datetime.now(
                    timezone.utc
                ).isoformat()
            self.save()
            return total

    def reset_module_session_stats(self) -> None:
        
        with self._lock:
            self._session_module_counts = {}
            self._session_cyberspaces = 0

    @staticmethod
    def _positive_interval(value, fallback: int) -> float:
        try:
            return max(1.0, float(value))
        except (TypeError, ValueError):
            return float(fallback)

    def cyberspace_progress(self) -> dict:
        
        with self._lock:
            stats = self.module_use_stats
            totals = {
                task: _nonnegative_int(self.module_counts.get(task, 0))
                for task in MODULE_USE_TASKS
            }
            baseline = stats.get("cyberspaceBaseline", {})
            since_last = {
                task: max(0, totals[task] - _nonnegative_int(baseline.get(task, 0)))
                for task in MODULE_USE_TASKS
            }
            attempts = sum(since_last.values())
            remaining = max(0, CYBERSPACE_ODDS - attempts)
            overdue = max(0, attempts - CYBERSPACE_ODDS)

            session_accounts = getattr(self, "_session_module_counts", {})
            session_totals = {
                task: sum(
                    _nonnegative_int(values.get(task, 0))
                    for values in session_accounts.values()
                    if isinstance(values, dict)
                )
                for task in MODULE_USE_TASKS
            }

            intervals_cfg = self.automation.get("intervals", {}) or {}
            intervals = {
                "strangeController": self._positive_interval(
                    intervals_cfg.get("strangeController"), 21 * 60
                ),
                "biomeRandomizer": self._positive_interval(
                    intervals_cfg.get("biomeRandomizer"), 36 * 60
                ),
            }
            enabled_ids = {
                str(account.get("id")) for account in self.enabled_accounts()
            }
            account_rows = []
            total_uses_per_hour = 0.0
            active_accounts = 0
            active_sources = 0

            for account in self.accounts:
                account_key = str(account.get("id"))
                lifetime = stats["accounts"].get(account_key, {})
                session = session_accounts.get(account_key, {})
                modules = account.get("modules") or {}
                participates = account_key in enabled_ids
                uses_per_hour = 0.0
                enabled_modules = {}
                for task in MODULE_USE_TASKS:
                    is_enabled = participates and bool(modules.get(task, False))
                    enabled_modules[task] = is_enabled
                    if is_enabled:
                        uses_per_hour += 3600.0 / intervals[task]
                        active_sources += 1
                if uses_per_hour > 0:
                    active_accounts += 1
                    total_uses_per_hour += uses_per_hour

                lifetime_values = {
                    task: _nonnegative_int(lifetime.get(task, 0))
                    for task in MODULE_USE_TASKS
                }
                session_values = {
                    task: _nonnegative_int(session.get(task, 0))
                    for task in MODULE_USE_TASKS
                }
                account_rows.append(
                    {
                        "id": account.get("id"),
                        "name": account.get("name") or f"Account {account.get('id')}",
                        "avatar": account.get("avatar", ""),
                        "enabled": participates,
                        "active": uses_per_hour > 0,
                        "modules": enabled_modules,
                        "lifetime": lifetime_values,
                        "session": session_values,
                        "combinedLifetime": sum(lifetime_values.values()),
                        "combinedSession": sum(session_values.values()),
                        "usesPerHour": round(uses_per_hour, 4),
                    }
                )

            attributed = {
                task: sum(row["lifetime"][task] for row in account_rows)
                for task in MODULE_USE_TASKS
            }
            unattributed = {
                task: max(0, totals[task] - attributed[task])
                for task in MODULE_USE_TASKS
            }

            chance = 0.0
            if attempts > 0:
                chance = (
                    -math.expm1(attempts * math.log1p(-1.0 / CYBERSPACE_ODDS)) * 100.0
                )




            eta_uses = remaining if remaining > 0 else CYBERSPACE_ODDS
            eta_seconds = None
            if total_uses_per_hour > 0:
                eta_seconds = eta_uses / (total_uses_per_hour / 3600.0)

            return {
                "odds": CYBERSPACE_ODDS,
                "cyberspaceCount": int(self.biome_counts.get("cyberspace", 0) or 0),
                "lifetime": {**totals, "combined": sum(totals.values())},
                "unattributed": {
                    **unattributed,
                    "combined": sum(unattributed.values()),
                },
                "session": {**session_totals, "combined": sum(session_totals.values())},
                "sinceLast": {**since_last, "combined": attempts},
                "estimatedRemaining": remaining,
                "averageCycleOverdue": overdue,
                "progressPercent": min(100.0, attempts / CYBERSPACE_ODDS * 100.0),
                "chanceSinceLastPercent": round(chance, 4),
                "etaSeconds": round(eta_seconds) if eta_seconds is not None else None,
                "etaMode": "averageCycle" if remaining > 0 else "fromNow",
                "usesPerHour": round(total_uses_per_hour, 4),
                "activeAccounts": active_accounts,
                "activeSources": active_sources,
                "intervals": {task: round(value) for task, value in intervals.items()},
                "accounts": account_rows,
                "lastCyberspace": stats.get("lastCyberspace", ""),
                "lastCyberspaceAccount": stats.get("lastCyberspaceAccount"),
                "trackingSince": stats.get("trackingSince", ""),
                "anchorReason": stats.get("anchorReason", "trackingStart"),
                "sessionCyberspaces": int(getattr(self, "_session_cyberspaces", 0)),
                "accurateSinceLastCyberspace": bool(
                    stats.get("accurateSinceLastCyberspace", True)
                ),
            }

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
            return {
                "count": es["count"],
                "lastFound": es["lastFound"],
                "log": list(es["log"]),
            }

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
            self.data["edenStats"] = {
                "count": 0,
                "lastFound": "",
                "log": [],
                "accountSeconds": {},
            }
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
            base = (
                max(candidate, ConfigManager._last_id, *existing)
                if existing
                else max(candidate, ConfigManager._last_id)
            )
            new_id = base + 1
            ConfigManager._last_id = new_id
            return new_id
