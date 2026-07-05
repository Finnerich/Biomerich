

import time

from . import biomes

def default_autopop() -> dict:
    return {
        "accounts": {},
        "ocrFailsafe": False,
        "amountRegion": None,
        "notifyUse": False,
        "notifyFail": False,
        "presets": {},
        "activePreset": "",
    }

def default_account_entry() -> dict:
    return {"enabled": False, "biomes": {}}

def biome_keys() -> list:
    return list(biomes.ALL_KEYS)

def is_valid_key(biome_key: str) -> bool:
    
    if not biome_key:
        return False
    return biome_key in biomes.ALL_KEYS or biomes.is_unknown(biome_key)

def _int_or(v):
    
    try:
        return int(v)
    except (TypeError, ValueError):
        return v

def _clean_item(it) -> dict:
    if not isinstance(it, dict):
        return {"name": "", "amount": 1, "all": False}
    name = str(it.get("name") or "").strip()
    try:
        amount = max(1, int(it.get("amount", 1)))
    except (TypeError, ValueError):
        amount = 1
    return {"name": name, "amount": amount, "all": bool(it.get("all"))}

def sanitize_biome_map(raw) -> dict:
    
    out = {}
    raw = raw if isinstance(raw, dict) else {}

    def _clean_entry(entry):
        items = entry.get("items") if isinstance(entry, dict) else None
        items = [_clean_item(i) for i in items] if isinstance(items, list) else []
        return {
            "enabled": bool(entry.get("enabled")) if isinstance(entry, dict) else False,
            "items": items,
        }

    for bkey in biome_keys():
        out[bkey] = _clean_entry(raw.get(bkey) or {})
    for bkey, entry in raw.items():
        if biomes.is_unknown(bkey) and bkey not in out:
            out[bkey] = _clean_entry(entry or {})
    return out

def sanitize_account_entry(raw) -> dict:
    
    raw = raw if isinstance(raw, dict) else {}
    return {
        "enabled": bool(raw.get("enabled", False)),
        "biomes": sanitize_biome_map(raw.get("biomes")),
    }

class AutoPopEngine:
    

    def __init__(self, config):
        self.config = config
        self._queue = []
        self._seen = set()
        self.phase = "idle"
        self.current_account = ""
        self.current_biome = ""
        self.pops = 0

    def _cfg(self) -> dict:
        auto = self.config.automation
        ap = auto.get("autopop")
        if not isinstance(ap, dict):
            ap = default_autopop()
            auto["autopop"] = ap
        return ap

    def _account_entry(self, acc_id) -> dict:
        return (self._cfg().get("accounts") or {}).get(str(acc_id)) or {}

    def _account_biome(self, acc_id, biome_key: str) -> dict:
        entry = (self._account_entry(acc_id).get("biomes") or {}).get(biome_key)
        return entry if isinstance(entry, dict) else {}

    def ocr_enabled(self) -> bool:
        return bool(self._cfg().get("ocrFailsafe"))

    def amount_region(self):
        r = self._cfg().get("amountRegion")
        if isinstance(r, (list, tuple)) and len(r) == 4:
            return tuple(int(v) for v in r)
        return None

    def notify_use(self) -> bool:
        return bool(self._cfg().get("notifyUse"))

    def notify_fail(self) -> bool:
        return bool(self._cfg().get("notifyFail"))

    def account_enabled(self, acc_id) -> bool:
        return bool(self._account_entry(acc_id).get("enabled", False))

    def is_active_for(self, acc_id, biome_key: str) -> bool:
        
        if not self.config.is_account_enabled(acc_id):
            return False
        if not self.account_enabled(acc_id):
            return False
        return bool(self._account_biome(acc_id, biome_key).get("enabled"))

    def items_for(self, acc_id, biome_key: str) -> list:
        items = self._account_biome(acc_id, biome_key).get("items") or []
        return [_clean_item(i) for i in items if str((i or {}).get("name") or "").strip()]

    def in_use(self) -> bool:
        
        accounts_map = self._cfg().get("accounts") or {}
        for acc_id, entry in accounts_map.items():
            if not isinstance(entry, dict) or not entry.get("enabled"):
                continue
            if not self.config.is_account_enabled(_int_or(acc_id)):
                continue
            for entry_b in (entry.get("biomes") or {}).values():
                if not isinstance(entry_b, dict) or not entry_b.get("enabled"):
                    continue
                items = entry_b.get("items") or []
                if any(str((i or {}).get("name") or "").strip() for i in items):
                    return True
        return False

    def amount_region_required_missing(self) -> bool:
        
        return self.in_use() and self.amount_region() is None

    def enqueue(self, acc_id, biome_key: str) -> bool:
        
        if biome_key in (None, "", "normal"):
            return False
        if not self.is_active_for(acc_id, biome_key):
            return False
        if not self.items_for(acc_id, biome_key):
            return False
        key = (acc_id, biome_key)
        if key in self._seen:
            return False
        self._seen.add(key)
        self._queue.append(key)
        print(f"[AutoPop] Queued for account {acc_id} on biome '{biome_key}'.")
        return True

    def has_pending(self) -> bool:
        return bool(self._queue)

    def pop_job(self):
        if not self._queue:
            return None
        job = self._queue.pop(0)
        self._seen.discard(job)
        return job

    def reset(self):
        self._queue.clear()
        self._seen.clear()
        self.phase = "idle"
        self.current_account = ""
        self.current_biome = ""
