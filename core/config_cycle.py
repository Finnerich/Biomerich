
from . import calibration  # noqa: F401  (used by some extracted methods)


class CycleConfigMixin:
    @staticmethod
    def _default_limbo_entry() -> dict:
        return {"path": "vip", "edenWatch": False, "edenInterval": 120}

    def _cycle(self) -> dict:
        cyc = self.automation.setdefault("cycle", {})
        cyc.setdefault("steps", [])
        cyc.setdefault("enabled", False)
        lim = cyc.setdefault("limbo", {})
        if not isinstance(lim.get("accounts"), dict):
            lim["accounts"] = {}
        return cyc

    def cycle_steps(self) -> list:
        steps = self._cycle().get("steps")
        return steps if isinstance(steps, list) else []

    def set_cycle(self, steps) -> bool:
        
        VALID = ("fishing", "switchNormal", "limboEden")
        with self._lock:
            valid_ids = {a.get("id") for a in self.accounts}
            clean = []
            for s in (steps or []):
                if not isinstance(s, dict):
                    continue
                t = str(s.get("type") or "fishing")
                if t not in VALID:
                    continue
                aid = s.get("accId")
                if aid not in valid_ids:
                    continue
                step = {"type": t, "accId": aid}
                if t == "fishing":
                    try:
                        step["minutes"] = max(1, min(1440, int(s.get("minutes", 30))))
                    except (TypeError, ValueError):
                        step["minutes"] = 30
                elif t == "limboEden":
                    step["afk"] = bool(s.get("afk", False))
                    try:
                        step["minutes"] = max(1, min(1440, int(s.get("minutes", 30))))
                    except (TypeError, ValueError):
                        step["minutes"] = 30
                clean.append(step)
            self._cycle()["steps"] = clean
            self.save()
            return True

    def set_cycle_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._cycle()["enabled"] = bool(enabled)
            self.save()

    def _limbo_account_entry(self, acc_id):
        if not self._find(self.accounts, acc_id):
            return None
        accs = self._cycle()["limbo"].setdefault("accounts", {})
        entry = accs.get(str(acc_id))
        if not isinstance(entry, dict):
            entry = self._default_limbo_entry()
            accs[str(acc_id)] = entry
        else:
            for k, v in self._default_limbo_entry().items():
                entry.setdefault(k, v)
        return entry

    def limbo_account_setting(self, acc_id) -> dict:
        with self._lock:
            entry = self._limbo_account_entry(acc_id)
            return dict(entry) if entry else dict(self._default_limbo_entry())

    def set_limbo_account_setting(self, acc_id, key: str, value) -> bool:
        with self._lock:
            entry = self._limbo_account_entry(acc_id)
            if entry is None:
                return False
            if key == "edenWatch":
                entry[key] = bool(value)
            elif key == "edenInterval":
                try:
                    entry[key] = max(30, min(3600, int(value)))
                except (TypeError, ValueError):
                    return False
            elif key == "path":
                entry[key] = str(value or "vip").strip() or "vip"
            else:
                return False
            self.save()
            return True

    def _eden(self) -> dict:
        e = self.automation.setdefault("eden", {})
        e.setdefault("account", None)
        e.setdefault("edenWatch", False)
        e.setdefault("edenInterval", 120)
        return e

    def set_eden_account(self, acc_id) -> bool:
        with self._lock:
            if acc_id is not None and not self._find(self.accounts, acc_id):
                return False
            self._eden()["account"] = acc_id
            self.save()
            return True

    def set_eden_setting(self, key: str, value) -> bool:
        with self._lock:
            e = self._eden()
            if key == "edenWatch":
                e[key] = bool(value)
            elif key == "edenInterval":
                try:
                    e[key] = max(30, min(3600, int(value)))
                except (TypeError, ValueError):
                    return False
            else:
                return False
            self.save()
            return True

