
import json

from . import calibration  # noqa: F401  (used by some extracted methods)


class AutopopConfigMixin:
    def _autopop(self) -> dict:
        from . import autopop as _ap
        auto = self.automation
        ap = auto.get("autopop")
        if not isinstance(ap, dict):
            ap = _ap.default_autopop()
            auto["autopop"] = ap
        for k, v in _ap.default_autopop().items():
            ap.setdefault(k, v)
        return ap

    def _autopop_account(self, acc_id):
        
        from . import autopop as _ap
        if not self._find(self.accounts, acc_id):
            return None
        accs = self._autopop().setdefault("accounts", {})
        entry = accs.get(str(acc_id))
        if not isinstance(entry, dict):
            entry = _ap.default_account_entry()
            accs[str(acc_id)] = entry
        entry.setdefault("enabled", False)
        if not isinstance(entry.get("biomes"), dict):
            entry["biomes"] = {}
        return entry

    def _autopop_account_biome(self, acc_id, biome_key: str):
        from . import autopop as _ap
        if not _ap.is_valid_key(biome_key):
            return None
        acc_entry = self._autopop_account(acc_id)
        if acc_entry is None:
            return None
        bmap = acc_entry["biomes"]
        entry = bmap.get(biome_key)
        if not isinstance(entry, dict):
            entry = {"enabled": False, "items": []}
            bmap[biome_key] = entry
        entry.setdefault("enabled", False)
        if not isinstance(entry.get("items"), list):
            entry["items"] = []
        return entry

    def set_autopop_account_biome_enabled(self, acc_id, biome_key: str, enabled: bool) -> bool:
        with self._lock:
            entry = self._autopop_account_biome(acc_id, biome_key)
            if entry is None:
                return False
            entry["enabled"] = bool(enabled)
            if not enabled:
                acc_entry = self._autopop_account(acc_id)
                if acc_entry is not None and not any(
                    b.get("enabled") for b in (acc_entry.get("biomes") or {}).values()
                    if isinstance(b, dict)
                ):
                    acc_entry["enabled"] = False
            self.save()
            return True

    def set_autopop_account_items(self, acc_id, biome_key: str, items) -> bool:
        from . import autopop as _ap
        with self._lock:
            entry = self._autopop_account_biome(acc_id, biome_key)
            if entry is None:
                return False
            clean = []
            if isinstance(items, list):
                for it in items:
                    clean.append(_ap._clean_item(it))
            entry["items"] = clean
            self.save()
            return True

    def set_autopop_option(self, key: str, value) -> bool:
        if key not in ("ocrFailsafe", "notifyUse", "notifyFail", "leaveLimboOnRareBiome"):
            return False
        with self._lock:
            self._autopop()[key] = bool(value)
            self.save()
            return True

    def set_autopop_amount_region(self, p1, p2) -> None:
        with self._lock:
            self._autopop()["amountRegion"] = calibration.region_from_points(p1, p2)
            self.save()

    def clear_autopop_amount_region(self) -> None:
        with self._lock:
            self._autopop()["amountRegion"] = None
            self.save()

    def set_autopop_account(self, acc_id, enabled: bool) -> bool:
        with self._lock:
            entry = self._autopop_account(acc_id)
            if entry is None:
                return False
            entry["enabled"] = bool(enabled)
            self.save()
            return True

    def save_autopop_preset(self, acc_id, name: str) -> bool:
        
        from . import autopop as _ap
        name = (name or "").strip()
        if not name:
            return False
        with self._lock:
            entry = self._autopop_account(acc_id)
            if entry is None:
                return False
            ap = self._autopop()
            snapshot = {"biomes": _ap.sanitize_biome_map(entry.get("biomes"))}
            ap.setdefault("presets", {})[name] = snapshot
            ap["activePreset"] = name
            self.save()
            return True

    def load_autopop_preset(self, acc_id, name: str) -> bool:
        
        from . import autopop as _ap
        with self._lock:
            entry = self._autopop_account(acc_id)
            if entry is None:
                return False
            ap = self._autopop()
            preset = (ap.get("presets") or {}).get(name)
            if not isinstance(preset, dict):
                return False
            entry["biomes"] = _ap.sanitize_biome_map(preset.get("biomes"))
            ap["activePreset"] = name
            self.save()
            return True

    def delete_autopop_preset(self, name: str) -> bool:
        with self._lock:
            ap = self._autopop()
            presets = ap.setdefault("presets", {})
            if name in presets:
                del presets[name]
                if ap.get("activePreset") == name:
                    ap["activePreset"] = ""
                self.save()
                return True
            return False

    def import_autopop_preset(self, name: str, payload) -> dict:
        from . import autopop as _ap
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (json.JSONDecodeError, TypeError):
                return {"ok": False, "error": "bad_json"}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "bad_payload"}
        biome_src = payload.get("biomes") if "biomes" in payload else payload
        name = (name or payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "no_name"}
        with self._lock:
            ap = self._autopop()
            ap.setdefault("presets", {})[name] = {
                "biomes": _ap.sanitize_biome_map(biome_src)
            }
            self.save()
            return {"ok": True, "name": name}

    def export_autopop_preset(self, name: str, acc_id=None) -> dict:
        
        from . import autopop as _ap
        with self._lock:
            ap = self._autopop()
            preset = (ap.get("presets") or {}).get(name)
            if not isinstance(preset, dict):
                entry = self._autopop_account(acc_id) if acc_id is not None else None
                preset = {"biomes": (entry or {}).get("biomes")}
            return {
                "name": name,
                "biomes": _ap.sanitize_biome_map(preset.get("biomes")),
            }

