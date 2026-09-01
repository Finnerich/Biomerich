

from __future__ import annotations

import json
import re
import threading
import time
import unicodedata

from .aura_catalog import AuraCatalog
from . import decision_trace


_RPC_MARKER = "[BloxstrapRPC]"
_EMPTY_AURAS = {"", "none", "_none_", "unequipped"}


def _rpc_payload(line: str):
    
    if not isinstance(line, str) or _RPC_MARKER not in line:
        return None
    start = line.find("{", line.find(_RPC_MARKER))
    if start < 0:
        return None
    try:
        payload, _end = json.JSONDecoder().raw_decode(line[start:])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def aura_state_from_rpc_line(line: str) -> tuple[bool, str | None]:
    
    payload = _rpc_payload(line)
    if not payload or str(payload.get("command", "")).casefold() != "setrichpresence":
        return False, None

    data = payload.get("data")
    state = data.get("state") if isinstance(data, dict) else None
    if not isinstance(state, str):
        return False, None



    state = state.replace("\\n", "\n").strip()
    match = re.match(r"^equipped\b(.*)$", state, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return False, None
    name = match.group(1).strip(" \t\r\n")
    if len(name) >= 2 and name[0] == name[-1] and name[0] in {'"', "'"}:
        name = name[1:-1].strip()
    if name.casefold() in _EMPTY_AURAS:
        return True, None
    return True, name or None


def aura_from_rpc_line(line: str):
    
    is_update, name = aura_state_from_rpc_line(line)
    return name if is_update else None


def aura_key(name: str) -> str:
    
    normalized = unicodedata.normalize("NFKC", str(name or "")).casefold()
    alphanumeric = "".join(char for char in normalized if char.isalnum())
    return alphanumeric or "".join(
        char for char in normalized if not char.isspace()
    )


def fallback_display_name(name: str) -> str:
    
    return re.sub(r"\s+", " ", str(name or "").replace("_", " ")).strip()


def _setting_number(value):
    
    try:
        number = int(str(value or "").replace(",", "").replace("_", "").strip())
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 10**18 else None


def _name_keys(value) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        key
        for part in re.split(r"[,\n;]+", value)
        if (key := aura_key(part))
    }


def _discord_user_id(value) -> str:
    user_id = str(value or "").strip()
    return user_id if re.fullmatch(r"\d{15,22}", user_id) else ""


def aura_delivery(event, settings) -> dict:
    
    event = event or {}
    settings = settings or {}
    event_keys = {
        aura_key(event.get("rawAura")),
        aura_key(event.get("aura")),
    }
    event_keys.discard("")
    known = bool(event.get("known"))
    rarity = event.get("rarity")

    minimum = _setting_number(settings.get("auraMinimumRarity"))
    always_send = _name_keys(settings.get("auraAlwaysSendNames"))
    send = (
        not known
        or minimum is None
        or (isinstance(rarity, int) and rarity >= minimum)
        or bool(event_keys & always_send)
    )

    ping_user_id = ""
    configured_id = _discord_user_id(settings.get("auraPingUserId"))
    if send and configured_id:
        ping_minimum = _setting_number(settings.get("auraPingMinimumRarity"))
        always_ping = _name_keys(settings.get("auraAlwaysPingNames"))
        should_ping = bool(event_keys & always_ping) or (
            known
            and ping_minimum is not None
            and isinstance(rarity, int)
            and rarity >= ping_minimum
        )
        if should_ping:
            ping_user_id = configured_id

    return {"send": send, "pingUserId": ping_user_id}


def aura_delivery_decision(event, settings, delivery, webhook_available=True) -> dict:
    
    event = event or {}
    settings = settings or {}
    delivery = delivery or {}
    name = event.get("aura") or fallback_display_name(event.get("rawAura")) or "Unknown aura"
    known = bool(event.get("known"))
    rarity = event.get("rarity")
    minimum = _setting_number(settings.get("auraMinimumRarity"))
    event_keys = {aura_key(event.get("rawAura")), aura_key(event.get("aura"))}
    event_keys.discard("")
    name_override = bool(event_keys & _name_keys(settings.get("auraAlwaysSendNames")))
    send_rule_passed = bool(delivery.get("send"))

    facts = [
        decision_trace.fact("Aura", name),
        decision_trace.fact("Catalog", "Known" if known else "Unknown"),
        decision_trace.fact("Detected rarity", f"1 in {rarity:,}" if isinstance(rarity, int) else "Not available"),
        decision_trace.fact("Minimum rarity", f"1 in {minimum:,}" if minimum else "Disabled"),
        decision_trace.fact("Discord ping", "Yes" if delivery.get("pingUserId") else "No"),
    ]
    checks = [
        decision_trace.check("Aura Detection is enabled", True),
        decision_trace.check("Aura equip event was detected", True),
        decision_trace.check("Webhook send rule passed", send_rule_passed),
        decision_trace.check("A webhook is routed to this account", webhook_available),
    ]

    if not send_rule_passed:
        return decision_trace.make(
            "skipped", "below_minimum_rarity", "Aura Detection",
            f"{name} was detected, but its rarity is below your minimum webhook rarity.",
            checks=checks, facts=facts,
            next_step={"label": "Open Aura Settings", "tab": "modules", "drawer": "aura"},
        )
    if not webhook_available:
        return decision_trace.make(
            "skipped", "no_webhook_routed", "Aura Detection",
            f"{name} passed your aura rules, but this account has no active routed webhook.",
            checks=checks, facts=facts,
            next_step={"label": "Open Webhooks", "tab": "webhooks"},
        )
    if not known:
        reason = "unknown_aura_fallback"
        summary = f"{name} was queued for Discord because unknown auras are never hidden by the rarity filter."
    elif name_override:
        reason = "always_send_override"
        summary = f"{name} was queued for Discord because it is in Always send these auras."
    elif minimum is None:
        reason = "minimum_rarity_disabled"
        summary = f"{name} was queued for Discord because no minimum webhook rarity is set."
    else:
        reason = "minimum_rarity_reached"
        summary = f"{name} was queued for Discord because it reached your minimum webhook rarity."
    return decision_trace.make(
        "acted", reason, "Aura Detection", summary,
        checks=checks, facts=facts,
    )


class AuraController:
    

    def __init__(self, catalog=None):
        self.catalog = catalog or AuraCatalog()
        self._last_real = {}
        self._log = []
        self._log_seq = 0
        self._lock = threading.RLock()

    def reset(self):
        
        with self._lock:
            self._last_real.clear()

    def seed_equipped(self, acc_id, raw_name):
        
        key = aura_key(raw_name)
        with self._lock:
            if key:
                self._last_real[acc_id] = key
            else:
                self._last_real.pop(acc_id, None)

    def refresh_catalog_async(self):
        return self.catalog.refresh_async()

    def aura_log(self, since_id=0):
        try:
            since_id = int(since_id or 0)
        except (TypeError, ValueError):
            since_id = 0
        with self._lock:
            return [dict(entry) for entry in self._log if entry["id"] > since_id]

    def process_line(self, acc_id, account_name, line, biome_key=None):
        
        raw_name = aura_from_rpc_line(line)
        if not raw_name:
            return None
        key = aura_key(raw_name)
        if not key:
            return None

        metadata = self.catalog.resolve(raw_name, biome_key)
        with self._lock:
            if self._last_real.get(acc_id) == key:
                return None
            self._last_real[acc_id] = key
            self._log_seq += 1
            event = {
                "id": self._log_seq,
                "accountId": acc_id,
                "account": str(account_name or "?"),
                "aura": metadata["displayName"] or fallback_display_name(raw_name),
                "rawAura": raw_name,
                "known": metadata["known"],
                "rarity": metadata["rarity"],
                "category": metadata["category"],
                "color": metadata["color"],
                "conditionLabel": metadata["conditionLabel"],
                "ts": time.time(),
            }
            self._log.append(event)
            if len(self._log) > 200:
                self._log = self._log[-200:]
            return dict(event)
