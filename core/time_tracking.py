import time
from datetime import datetime

TIME_MODULES = ("biomeLogging", "antiAfk", "ramTrim", "strangeController",
                "biomeRandomizer", "merchantTeleporter", "auraDetection",
                "autopop", "fishing")
AUTOMATION_ONLY = ("strangeController", "biomeRandomizer", "merchantTeleporter",
                   "auraDetection", "autopop", "fishing")
FLUSH_THROTTLE = 15.0

def default_tracking() -> dict:
    return {
        "totalEngine": 0.0,
        "idle": 0.0,
        "automation": 0.0,
        "modules": {k: 0.0 for k in TIME_MODULES},
        "sessions": 0,
        "longestSession": 0.0,
        "firstStart": "",
        "lastStart": "",
        "fishCaught": 0,
    }

class TimeTracker:
    def __init__(self, config):
        self.config = config
        self._seg_start = None
        self._seg_mode = "idle"
        self._seg_modules = ()
        self._session_start = None
        self._last_flush = 0.0

    def _store(self) -> dict:
        return self.config.time_tracking()

    def _enabled_modules(self) -> tuple:
        s = self.config.settings
        a = self.config.automation
        mods = []
        if s.get("biomeLogging"):
            mods.append("biomeLogging")
        if s.get("antiAfkEnabled"):
            mods.append("antiAfk")
        if s.get("ramTrimEnabled"):
            mods.append("ramTrim")
        if a.get("strangeController"):
            mods.append("strangeController")
        if a.get("biomeRandomizer"):
            mods.append("biomeRandomizer")
        if a.get("merchantTeleporter") or any(
            (acc.get("modules") or {}).get("merchantTeleporter")
            for acc in (self.config.enabled_accounts() if hasattr(self.config, "enabled_accounts") else [])
        ):
            mods.append("merchantTeleporter")
        enabled_accounts = (self.config.enabled_accounts()
                            if hasattr(self.config, "enabled_accounts") else [])
        if any((acc.get("modules") or {}).get("auraDetection")
               for acc in enabled_accounts):
            mods.append("auraDetection")
        enabled_ids = {str(acc.get("id")) for acc in enabled_accounts}
        autopop_accounts = ((a.get("autopop") or {}).get("accounts") or {})
        if any(str(acc_id) in enabled_ids and entry.get("enabled")
               for acc_id, entry in autopop_accounts.items()
               if isinstance(entry, dict)):
            mods.append("autopop")
        fishing = a.get("fishing") or {}
        if fishing.get("enabled") or fishing.get("moduleEnabled") or any(
            (acc.get("modules") or {}).get("fishing") for acc in enabled_accounts
        ):
            mods.append("fishing")
        return tuple(mods)

    def _active_in(self, mode, mods) -> list:
        out = []
        for m in mods:
            if m in AUTOMATION_ONLY:
                if mode == "automation":
                    out.append(m)
            else:
                out.append(m)
        return out

    def _open(self, mode, now):
        self._seg_start = now
        self._seg_mode = "automation" if mode == "automation" else "idle"
        self._seg_modules = self._enabled_modules()

    def _close(self, now):
        if self._seg_start is None:
            return
        d = max(0.0, now - self._seg_start)
        if d > 0:
            store = self._store()
            store["totalEngine"] = store.get("totalEngine", 0.0) + d
            store[self._seg_mode] = store.get(self._seg_mode, 0.0) + d
            mods = store.setdefault("modules", {})
            for m in self._active_in(self._seg_mode, self._seg_modules):
                mods[m] = mods.get(m, 0.0) + d
        self._seg_start = None

    def start(self, mode):
        now = time.time()
        self._session_start = now
        self._last_flush = now
        self._open(mode, now)
        store = self._store()
        store["sessions"] = int(store.get("sessions", 0)) + 1
        iso = datetime.now().isoformat(timespec="seconds")
        if not store.get("firstStart"):
            store["firstStart"] = iso
        store["lastStart"] = iso
        self.config.save()

    def note_mode_change(self, mode):
        if self._seg_start is None:
            return
        now = time.time()
        self._close(now)
        self._open(mode, now)
        self.config.save()

    def flush(self, force=False):
        if self._seg_start is None:
            return
        now = time.time()
        if not force and (now - self._last_flush) < FLUSH_THROTTLE:
            return
        mode = self._seg_mode
        self._close(now)
        self._open(mode, now)
        self._last_flush = now
        self.config.save()

    def stop(self):
        if self._seg_start is None:
            return
        now = time.time()
        session_len = now - (self._session_start or now)
        self._close(now)
        store = self._store()
        if session_len > store.get("longestSession", 0.0):
            store["longestSession"] = session_len
        self._session_start = None
        self.config.save()

    def live(self) -> dict:
        store = self._store()
        out = {
            "totalEngine": store.get("totalEngine", 0.0),
            "idle": store.get("idle", 0.0),
            "automation": store.get("automation", 0.0),
            "modules": dict(store.get("modules", {})),
            "sessions": int(store.get("sessions", 0)),
            "longestSession": store.get("longestSession", 0.0),
            "firstStart": store.get("firstStart", ""),
            "lastStart": store.get("lastStart", ""),
            "fishCaught": int(store.get("fishCaught", 0)),
            "running": self._seg_start is not None,
            "activeMode": self._seg_mode if self._seg_start is not None else "",
            "activeModules": [],
        }
        for k in TIME_MODULES:
            out["modules"].setdefault(k, 0.0)
        if self._seg_start is not None:
            now = time.time()
            d = max(0.0, now - self._seg_start)



            active = self._active_in(self._seg_mode, self._enabled_modules())
            out["activeModules"] = active
            out["totalEngine"] += d
            out[self._seg_mode] += d
            for m in active:
                out["modules"][m] = out["modules"].get(m, 0.0) + d
        return out
