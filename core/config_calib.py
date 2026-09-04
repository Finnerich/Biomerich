
from . import calibration  # noqa: F401  (used by some extracted methods)


class CalibConfigMixin:
    def _extra_calib(self) -> dict:
        return self.automation.setdefault("calib", {})

    def _extra_group(self, group: str) -> dict:
        ec = self._extra_calib()
        g = ec.setdefault(group, {})
        if not isinstance(g, dict):
            g = {}
            ec[group] = g
        return g

    def set_extra_pixel(self, group: str, slot: str, xy) -> None:
        from . import extra_calibrations as _ec
        if slot not in _ec.point_keys(group):
            return
        with self._lock:
            pixels = self._extra_group(group).setdefault("pixels", {})
            if xy is None:
                pixels[slot] = None
            else:
                pixels[slot] = [int(xy[0]), int(xy[1])]
            self.save()

    def clear_extra_pixel(self, group: str, slot: str) -> None:
        with self._lock:
            pixels = self._extra_group(group).setdefault("pixels", {})
            pixels[slot] = None
            self.save()

    def set_extra_region(self, group: str, name: str, p1, p2) -> None:
        from . import extra_calibrations as _ec
        if name not in _ec.region_keys(group):
            return
        with self._lock:
            regions = self._extra_group(group).setdefault("regions", {})
            regions[name] = calibration.region_from_points(p1, p2)
            self.save()

    def clear_extra_region(self, group: str, name: str) -> None:
        with self._lock:
            regions = self._extra_group(group).setdefault("regions", {})
            regions[name] = None
            self.save()

    def load_extra_preset(self, name: str) -> bool:
        from . import extra_presets, extra_calibrations as _ec
        data = extra_presets.get_preset(name)
        if not data:
            return False
        with self._lock:
            calib = self._extra_calib()
            for g in _ec.groups():
                gkey = g["key"]
                gdata = data.get(gkey) or {}
                gc = calib.setdefault(gkey, {})
                gp = gc.setdefault("pixels", {})
                for slot, pos in (gdata.get("pixels") or {}).items():
                    if isinstance(pos, (list, tuple)) and len(pos) == 2:
                        gp[slot] = [int(pos[0]), int(pos[1])]
                gr = gc.setdefault("regions", {})
                for nm, box in (gdata.get("regions") or {}).items():
                    if isinstance(box, (list, tuple)) and len(box) == 4:
                        gr[nm] = [int(value) for value in box]
            self.automation.setdefault("calib_preset", name)
            self.automation["calib_preset"] = name
            self.save()
            return True

