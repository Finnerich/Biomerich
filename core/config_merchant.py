
from . import calibration  # noqa: F401  (used by some extracted methods)


class MerchantConfigMixin:
    def set_merchant_interval(self, value) -> None:
        with self._lock:
            try:
                v = max(30, int(value))
            except (TypeError, ValueError):
                return
            intervals = self.automation.setdefault("intervals", {})
            intervals["merchantTeleporter"] = v
            self.save()

    def _merchant_calib(self) -> dict:
        merch = self.automation.setdefault("merchants", {})
        calib = merch.setdefault("calib", {})
        if not isinstance(calib, dict):
            calib = {}
            merch["calib"] = calib
        return calib

    def _merchant_group(self, group: str) -> dict:
        calib = self._merchant_calib()
        g = calib.setdefault(group, {})
        if not isinstance(g, dict):
            g = {}
            calib[group] = g
        return g

    def set_merchant_pixel(self, group: str, slot: str, xy) -> None:
        from . import merchants_data
        if slot not in merchants_data.calib_point_keys(group):
            return
        with self._lock:
            pixels = self._merchant_group(group).setdefault("pixels", {})
            pixels[slot] = calibration.as_point(xy)
            self.save()

    def clear_merchant_pixel(self, group: str, slot: str) -> None:
        with self._lock:
            pixels = self._merchant_group(group).setdefault("pixels", {})
            pixels[slot] = None
            self.save()

    def set_merchant_region(self, group: str, name: str, p1, p2) -> None:
        from . import merchants_data
        if name not in merchants_data.calib_region_keys(group):
            return
        with self._lock:
            regions = self._merchant_group(group).setdefault("regions", {})
            regions[name] = calibration.region_from_points(p1, p2)
            self.save()

    def clear_merchant_region(self, group: str, name: str) -> None:
        with self._lock:
            regions = self._merchant_group(group).setdefault("regions", {})
            regions[name] = None
            self.save()

    def load_merchant_preset(self, name: str) -> bool:
        from . import merchant_presets, merchants_data
        data = merchant_presets.get_preset(name)
        if not data:
            return False
        with self._lock:
            calib = self._merchant_calib()
            for gkey in merchants_data.calib_group_keys():
                gdata = data.get(gkey) or {}
                g = calib.setdefault(gkey, {})
                gp = g.setdefault("pixels", {})
                for slot, pos in (gdata.get("pixels") or {}).items():
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        gp[slot] = [int(pos[0]), int(pos[1])]
                gr = g.setdefault("regions", {})
                for nm, box in (gdata.get("regions") or {}).items():
                    if isinstance(box, (list, tuple)) and len(box) == 4:
                        gr[nm] = [int(value) for value in box]
            self.automation.setdefault("merchants", {})["preset"] = name
            self.save()
            return True


    MERCHANT_BUY_LOG_MAX = 500

    def _merchant_autobuy_account(self, acc_id) -> dict:
        from . import merchants_data
        merch = self.automation.setdefault("merchants", {})
        ab = merch.setdefault("autobuy", {})
        if not isinstance(ab, dict):
            ab = {}
            merch["autobuy"] = ab
        accs = ab.setdefault("accounts", {})
        if not isinstance(accs, dict):
            accs = {}
            ab["accounts"] = accs
        entry = accs.setdefault(str(acc_id), {})
        if not isinstance(entry, dict):
            entry = {}
            accs[str(acc_id)] = entry
        for mid in merchants_data.AUTOBUY_MERCHANTS:
            e = entry.setdefault(mid, {})
            if not isinstance(e, dict):
                e = {}
                entry[mid] = e
            e.setdefault("enabled", False)
            if not isinstance(e.get("items"), list):
                e["items"] = []
        return entry

    def merchant_autobuy(self, acc_id, mid) -> dict:
        return self._merchant_autobuy_account(acc_id).get(mid) or {"enabled": False, "items": []}

    def set_merchant_autobuy_enabled(self, acc_id, mid, enabled) -> None:
        from . import merchants_data
        if mid not in merchants_data.AUTOBUY_MERCHANTS:
            return
        with self._lock:
            self._merchant_autobuy_account(acc_id)[mid]["enabled"] = bool(enabled)
            self.save()

    def set_merchant_autobuy_items(self, acc_id, mid, items) -> None:
        
        from . import merchants_data
        if mid not in merchants_data.AUTOBUY_MERCHANTS:
            return
        allowed = set(merchants_data.autobuy_items(mid))
        clean, seen = [], set()
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()
            if name not in allowed or name in seen:
                continue
            try:
                amount = max(0, int(it.get("amount", 1)))
            except (TypeError, ValueError):
                amount = 1
            seen.add(name)
            clean.append({"name": name, "amount": amount, "all": bool(it.get("all"))})
        with self._lock:
            entry = self._merchant_autobuy_account(acc_id)[mid]
            entry["items"] = clean
            if not any(i["all"] or i["amount"] > 0 for i in clean):
                entry["enabled"] = False
            self.save()

    def decrement_merchant_autobuy(self, acc_id, mid, name, n) -> tuple:
        
        with self._lock:
            entry = self._merchant_autobuy_account(acc_id).get(mid) or {}
            for it in entry.get("items", []):
                if it.get("name") == name:
                    try:
                        before = max(0, int(it.get("amount", 0)))
                    except (TypeError, ValueError):
                        before = 0
                    left = max(0, before - max(0, int(n)))
                    it["amount"] = left
                    if not any(
                        x.get("all") or int(x.get("amount", 0) or 0) > 0
                        for x in entry.get("items", [])
                    ):
                        entry["enabled"] = False
                    self.save()
                    return (before, left)
            return (0, 0)

    def merchant_buy_log(self) -> list:
        merch = self.automation.setdefault("merchants", {})
        log = merch.setdefault("buyLog", [])
        if not isinstance(log, list):
            log = []
            merch["buyLog"] = log
        return log

    def add_merchant_buy(self, acc_id, mid, item, amount) -> dict:
        from datetime import datetime
        with self._lock:
            acc = self._find(self.accounts, acc_id)
            log = self.merchant_buy_log()
            entry = {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "account": (acc or {}).get("name", "?"),
                "merchant": str(mid),
                "item": str(item),
                "amount": max(0, int(amount)),
            }
            log.append(entry)
            del log[:-self.MERCHANT_BUY_LOG_MAX]
            self.save()
            return entry

    def reset_merchant_buy_log(self) -> None:
        with self._lock:
            self.automation.setdefault("merchants", {})["buyLog"] = []
            self.save()

