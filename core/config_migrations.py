

from . import biomes


def default_fishing_entry() -> dict:
    return {
        "autoSell": False,
        "sellAfter": 20,
        "sellCycle": 1,
        "route": "None",
        "primeRoute": False,
        "sellOnStart": False,
    }


def migrate_unknown_biomes(cfg: dict) -> bool:
    
    changed = False
    unknown = cfg.get("unknownBiomes") or {}
    counts = cfg.get("biomeCounts") or {}
    for name in list(unknown.keys()):
        key = biomes.normalize_hover(name)
        if key and key in counts and not biomes.is_unknown(key):
            counts[key] = int(counts.get(key, 0)) + int(unknown.get(name, 0) or 0)
            del unknown[name]
            changed = True
            print(f"[Biomes] Merged unknown '{name}' into known biome '{key}'.")
    return changed


def migrate_fishing(cfg: dict) -> bool:
    
    changed = False
    fishing = cfg["automation"].setdefault("fishing", {})
    accs = fishing.setdefault("accounts", {})
    if not isinstance(accs, dict):
        accs = {}
        fishing["accounts"] = accs
    legacy = {k: fishing.pop(k) for k in ("autoSell", "sellAfter", "sellCycle", "route") if k in fishing}
    if legacy:
        base = default_fishing_entry()
        base["autoSell"] = bool(legacy.get("autoSell", False))
        try:
            base["sellAfter"] = max(1, int(legacy.get("sellAfter", 20)))
        except (TypeError, ValueError):
            pass
        try:
            base["sellCycle"] = max(1, int(legacy.get("sellCycle", 1)))
        except (TypeError, ValueError):
            pass
        base["route"] = str(legacy.get("route") or "None")
        for acc in cfg["accounts"]:
            sid = str(acc.get("id"))
            if not isinstance(accs.get(sid), dict):
                accs[sid] = dict(base)
        changed = True
    fishing.setdefault("webhookEnabled", False)
    if "schedule" not in fishing:
        acc = fishing.get("account")
        fishing["schedule"] = [{"accId": acc, "minutes": 30}] if acc is not None else []
        changed = True
    if not isinstance(fishing.get("schedule"), list):
        fishing["schedule"] = []
    return changed


def migrate_cycle(cfg: dict) -> bool:
    
    changed = False
    auto = cfg["automation"]
    fishing = auto.get("fishing", {}) or {}
    cycle = auto.get("cycle")
    if not isinstance(cycle, dict):
        cycle = {}
        auto["cycle"] = cycle
    first_time = "steps" not in cycle
    if not isinstance(cycle.get("steps"), list):
        cycle["steps"] = []
    limbo = cycle.get("limbo")
    if not isinstance(limbo, dict):
        limbo = {}
        cycle["limbo"] = limbo
    if not isinstance(limbo.get("accounts"), dict):
        limbo["accounts"] = {}
    if first_time:
        steps = []
        for e in (fishing.get("schedule") or []):
            if isinstance(e, dict) and e.get("accId") is not None:
                try:
                    mins = max(1, int(e.get("minutes", 30)))
                except (TypeError, ValueError):
                    mins = 30
                steps.append({"type": "fishing", "accId": e.get("accId"), "minutes": mins})
        cycle["steps"] = steps
        cycle["enabled"] = bool(fishing.get("enabled", False))
        changed = True
    cycle.setdefault("enabled", False)
    return changed


def migrate_autopop(cfg: dict, ap: dict) -> bool:
    
    from . import autopop as _ap
    changed = False
    legacy = ap.pop("biomes", None)
    accs_map = ap.setdefault("accounts", {})
    if isinstance(legacy, dict) and legacy:
        base = _ap.sanitize_biome_map(legacy)
        has_usable = any(
            e["enabled"] and any(i["name"] for i in e["items"])
            for e in base.values()
        )
        for acc in cfg["accounts"]:
            sid = str(acc.get("id"))
            old = accs_map.get(sid) if isinstance(accs_map.get(sid), dict) else {}
            old_enabled = bool(old.get("enabled", True))
            overrides = old.get("biomes") if isinstance(old.get("biomes"), dict) else {}
            per = {}
            for bkey, entry in base.items():
                enabled = entry["enabled"] and overrides.get(bkey) is not False
                per[bkey] = {"enabled": enabled,
                             "items": [dict(i) for i in entry["items"]]}
            accs_map[sid] = {"enabled": old_enabled and has_usable, "biomes": per}
        changed = True
    for sid in list(accs_map.keys()):
        entry = accs_map[sid]
        bmap = entry.get("biomes") if isinstance(entry, dict) else None
        if isinstance(bmap, dict) and any(isinstance(v, bool) for v in bmap.values()):
            entry = {"enabled": bool(entry.get("enabled", False)), "biomes": {}}
        accs_map[sid] = _ap.sanitize_account_entry(entry)
    return changed
