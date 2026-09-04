
from . import calibration  # noqa: F401  (used by some extracted methods)


class FishingConfigMixin:
    def _fishing(self) -> dict:
        return self.automation.setdefault("fishing", {})

    def set_fishing(self, key: str, value) -> None:
        with self._lock:
            self._fishing()[key] = value
            self.save()

    def _fishing_account_entry(self, acc_id):
        if not self._find(self.accounts, acc_id):
            return None
        accs = self._fishing().setdefault("accounts", {})
        entry = accs.get(str(acc_id))
        if not isinstance(entry, dict):
            entry = self._default_fishing_entry()
            accs[str(acc_id)] = entry
        return entry

    def set_fishing_account_setting(self, acc_id, key: str, value) -> bool:
        with self._lock:
            entry = self._fishing_account_entry(acc_id)
            if entry is None:
                return False
            if key in ("autoSell", "primeRoute", "sellOnStart"):
                entry[key] = bool(value)



                if bool(value) and key == "primeRoute":
                    entry["sellOnStart"] = False
                elif bool(value) and key == "sellOnStart":
                    entry["primeRoute"] = False
            elif key == "sellAfter":
                try:
                    entry[key] = max(1, min(500, int(value)))
                except (TypeError, ValueError):
                    return False
            elif key == "sellCycle":
                try:
                    entry[key] = max(1, min(56, int(value)))
                except (TypeError, ValueError):
                    return False
            elif key == "route":
                entry[key] = str(value or "None").strip() or "None"
            else:
                return False
            self.save()
            return True

    def set_fishing_pixel(self, slot: str, xy) -> None:
        from . import fishing_presets
        if slot not in fishing_presets.slot_keys():
            return
        with self._lock:
            pixels = self._fishing().setdefault("pixels", {})
            if xy is None:
                pixels[slot] = None
            else:
                pixels[slot] = [int(xy[0]), int(xy[1])]
            self.save()

    def load_fishing_preset(self, name: str) -> bool:
        from . import fishing_presets
        coords = fishing_presets.get_preset(name)
        if not coords:
            return False
        with self._lock:
            pixels = self._fishing().setdefault("pixels", {})
            for slot, pos in coords.items():
                pixels[slot] = [int(pos[0]), int(pos[1])]


            region_boxes = fishing_presets.get_preset_regions(name)
            if region_boxes:
                regions = self._fishing().setdefault("regions", {})
                for rname, box in region_boxes.items():
                    regions[rname] = list(box)
            self._fishing()["preset"] = name
            self.save()
            return True

    def set_fishing_region(self, name: str, p1, p2) -> None:
        from . import fishing_presets
        if name not in fishing_presets.region_keys():
            return
        with self._lock:
            regions = self._fishing().setdefault("regions", {})
            regions[name] = calibration.region_from_points(p1, p2)
            self.save()

    def clear_fishing_region(self, name: str) -> None:
        with self._lock:
            regions = self._fishing().setdefault("regions", {})
            regions[name] = None
            self.save()

    def set_first_item_region(self, p1, p2) -> None:

        with self._lock:
            region = calibration.region_from_points(p1, p2)
            self.automation["firstItemRegion"] = region
            self.automation.setdefault("pixels", {})["first_item_slot"] = calibration.region_center(region)
            self.save()

    def clear_first_item_region(self) -> None:
        with self._lock:
            self.automation["firstItemRegion"] = None
            self.automation.setdefault("pixels", {})["first_item_slot"] = None
            self.save()

