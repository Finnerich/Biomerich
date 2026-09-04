

from __future__ import annotations

import json
import math

from . import extra_calibrations, fishing_presets, merchants_data, presets


FORMAT = "solrich-calibrations"
SCHEMA_VERSION = 1


def expected_schema():
    merchant = {}
    for group in merchants_data.calib_groups():
        merchant[group["key"]] = {
            "pixels": {key: 2 for key, _label in group.get("points", [])},
            "regions": {key: 4 for key, _label in group.get("regions", [])},
        }

    extra = {}
    for group in extra_calibrations.groups():
        points = list(group.get("points", []))
        regions = list(group.get("regions", []))
        for subgroup in group.get("subgroups", []):
            points.extend(subgroup.get("points", []))
            regions.extend(subgroup.get("regions", []))
        extra[group["key"]] = {
            "pixels": {key: 2 for key, _label in points},
            "regions": {key: 4 for key, _label in regions},
        }

    return {
        "inventory": {
            "pixels": {key: 2 for key in presets.slot_keys()},
            "regions": {
                "first_item_region": 4,
                "autopop_amount_region": 4,
            },
        },
        "fishing": {
            "pixels": {key: 2 for key in fishing_presets.slot_keys()},
            "regions": {key: 4 for key in fishing_presets.region_keys()},
        },
        "merchants": merchant,
        "extra": extra,
    }


def _coordinate(value, length):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return None
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(float(item))
        for item in value
    ):
        return None
    result = [int(round(item)) for item in value]
    if length == 4 and (result[2] <= 0 or result[3] <= 0):
        return None
    return result


def _value_at(mapping, *path):
    value = mapping
    for part in path:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def export_payload(automation):
    automation = automation if isinstance(automation, dict) else {}
    fish = automation.get("fishing") or {}
    merchants = (automation.get("merchants") or {}).get("calib") or {}
    extra = automation.get("calib") or {}
    schema = expected_schema()

    calibrations = {
        "inventory": {
            "pixels": dict(automation.get("pixels") or {}),
            "regions": {
                "first_item_region": automation.get("firstItemRegion"),
                "autopop_amount_region": (automation.get("autopop") or {}).get("amountRegion"),
            },
        },
        "fishing": {
            "pixels": dict(fish.get("pixels") or {}),
            "regions": dict(fish.get("regions") or {}),
        },
        "merchants": merchants,
        "extra": extra,
    }



    def clean(expected, supplied):
        if isinstance(expected, int):
            return _coordinate(supplied, expected)
        source = supplied if isinstance(supplied, dict) else {}
        return {key: clean(child, source.get(key)) for key, child in expected.items()}

    return {
        "format": FORMAT,
        "schemaVersion": SCHEMA_VERSION,
        "calibrations": clean(schema, calibrations),
    }


def export_text(automation):
    return json.dumps(export_payload(automation), indent=2, ensure_ascii=False)


def inspect_text(text):
    if not isinstance(text, str) or not text.strip():
        return _error("empty", "Paste calibration JSON first.")
    if len(text) > 2_000_000:
        return _error("too_large", "Calibration text is too large.")
    try:
        payload = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return _error("invalid_json", "This is not valid calibration JSON.")
    if not isinstance(payload, dict):
        return _error("invalid_format", "The calibration root must be an object.")
    if payload.get("format") not in (None, FORMAT):
        return _error("invalid_format", "This is not a SolRich calibration export.")

    supplied = payload.get("calibrations", payload)
    if not isinstance(supplied, dict):
        return _error("invalid_format", "The calibrations field must be an object.")

    missing, invalid, unknown = [], [], []

    def missing_leaves(expected, path):
        if isinstance(expected, int):
            missing.append(path)
            return
        for key, child in expected.items():
            missing_leaves(child, f"{path}.{key}" if path else key)

    def validate(expected, source, path=""):
        if isinstance(expected, int):
            if source is None:
                missing.append(path)
                return None
            value = _coordinate(source, expected)
            if value is None:
                invalid.append(f"{path} (expected {expected} numbers)")
            return value
        if not isinstance(source, dict):
            missing_leaves(expected, path)
            if source is not None:
                invalid.append(f"{path} (expected an object)")
            return {}
        result = {}
        for key, child in expected.items():
            child_path = f"{path}.{key}" if path else key
            result[key] = validate(child, source.get(key), child_path)
        for key in source:
            if key not in expected:
                unknown.append(f"{path}.{key}" if path else str(key))
        return result

    normalized = validate(expected_schema(), supplied)

    def count_valid(node):
        if isinstance(node, list):
            return 1
        if isinstance(node, dict):
            return sum(count_valid(value) for value in node.values())
        return 0

    valid_count = count_valid(normalized)
    def count_expected(node):
        if isinstance(node, int):
            return 1
        return sum(count_expected(value) for value in node.values())

    expected_count = count_expected(expected_schema())
    return {
        "ok": True,
        "canApply": valid_count > 0,
        "validCount": valid_count,
        "expectedCount": expected_count,
        "missing": missing,
        "invalid": invalid,
        "unknown": unknown,
        "normalized": normalized,
        "error": None,
        "message": None,
    }


def apply_to_automation(automation, normalized):
    
    if not isinstance(automation, dict) or not isinstance(normalized, dict):
        return 0
    applied = 0

    def merge(target, source):
        nonlocal applied
        if not isinstance(source, dict):
            return
        for key, value in source.items():
            if isinstance(value, list):
                target[key] = list(value)
                applied += 1

    inventory = normalized.get("inventory") or {}
    merge(automation.setdefault("pixels", {}), inventory.get("pixels") or {})
    inv_regions = inventory.get("regions") or {}
    first_item = inv_regions.get("first_item_region")
    if isinstance(first_item, list):
        automation["firstItemRegion"] = list(first_item)
        x, y, width, height = first_item
        automation.setdefault("pixels", {})["first_item_slot"] = [
            x + width // 2,
            y + height // 2,
        ]
        applied += 1
    amount = inv_regions.get("autopop_amount_region")
    if isinstance(amount, list):
        automation.setdefault("autopop", {})["amountRegion"] = list(amount)
        applied += 1

    fishing = normalized.get("fishing") or {}
    fish_target = automation.setdefault("fishing", {})
    merge(fish_target.setdefault("pixels", {}), fishing.get("pixels") or {})
    merge(fish_target.setdefault("regions", {}), fishing.get("regions") or {})

    merchant_source = normalized.get("merchants") or {}
    merchant_target = automation.setdefault("merchants", {}).setdefault("calib", {})
    for group, values in merchant_source.items():
        group_target = merchant_target.setdefault(group, {})
        merge(group_target.setdefault("pixels", {}), (values or {}).get("pixels") or {})
        merge(group_target.setdefault("regions", {}), (values or {}).get("regions") or {})

    extra_source = normalized.get("extra") or {}
    extra_target = automation.setdefault("calib", {})
    for group, values in extra_source.items():
        group_target = extra_target.setdefault(group, {})
        merge(group_target.setdefault("pixels", {}), (values or {}).get("pixels") or {})
        merge(group_target.setdefault("regions", {}), (values or {}).get("regions") or {})
    return applied


def _error(error, message):
    return {
        "ok": False,
        "canApply": False,
        "validCount": 0,
        "expectedCount": 0,
        "missing": [],
        "invalid": [],
        "unknown": [],
        "normalized": {},
        "error": error,
        "message": message,
    }
