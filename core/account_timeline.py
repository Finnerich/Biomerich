

from __future__ import annotations

import atexit
import json
import os
import re
import threading
import time
from pathlib import Path

from .config import get_config_dir


MAX_ENTRIES = 3000
_FILE_NAME = "account_timeline.json"
_lock = threading.RLock()
_entries: list[dict] = []
_seq = 0
_loaded = False
_save_timer = None
_path_override: Path | None = None

_DECISION_STATUSES = {"acted", "skipped", "blocked", "waiting", "cancelled", "failed"}
_CHECK_STATES = {"pass", "fail", "info"}


def _path() -> Path:
    return _path_override or (get_config_dir() / _FILE_NAME)


def _clean(value, limit=500) -> str:
    text = " ".join(str(value or "").replace("\x00", "").split())[:limit]


    text = re.sub(r"(?i)(_?\.ROBLOSECURITY\s*[=:]\s*)\S+", r"\1[redacted]", text)
    return text


def _clean_decision(value) -> dict | None:
    
    if not isinstance(value, dict):
        return None
    status = _clean(value.get("status"), 20).casefold()
    summary = _clean(value.get("summary"), 500)
    if status not in _DECISION_STATUSES or not summary:
        return None
    decision = {
        "status": status,
        "reasonCode": _clean(value.get("reasonCode"), 80).casefold(),
        "module": _clean(value.get("module"), 80),
        "summary": summary,
    }
    checks = []
    for raw in value.get("checks", []) if isinstance(value.get("checks"), list) else []:
        if not isinstance(raw, dict) or len(checks) >= 12:
            continue
        label = _clean(raw.get("label"), 120)
        state = _clean(raw.get("state"), 12).casefold()
        if not label or state not in _CHECK_STATES:
            continue
        check = {"label": label, "state": state}
        detail = _clean(raw.get("detail"), 240)
        if detail:
            check["detail"] = detail
        checks.append(check)
    if checks:
        decision["checks"] = checks

    facts = []
    for raw in value.get("facts", []) if isinstance(value.get("facts"), list) else []:
        if not isinstance(raw, dict) or len(facts) >= 12:
            continue
        label = _clean(raw.get("label"), 80)
        fact_value = _clean(raw.get("value"), 160)
        if label and fact_value:
            facts.append({"label": label, "value": fact_value})
    if facts:
        decision["facts"] = facts

    raw_next = value.get("nextStep")
    if isinstance(raw_next, dict):
        label = _clean(raw_next.get("label"), 80)
        tab = _clean(raw_next.get("tab"), 40)
        anchor = _clean(raw_next.get("anchor"), 80)
        if label and tab:
            decision["nextStep"] = {"label": label, "tab": tab}
            if anchor:
                decision["nextStep"]["anchor"] = anchor
            drawer = _clean(raw_next.get("drawer"), 40)
            if drawer:
                decision["nextStep"]["drawer"] = drawer
            try:
                account_id = int(raw_next.get("accountId"))
            except (TypeError, ValueError):
                account_id = None
            if account_id is not None:
                decision["nextStep"]["accountId"] = account_id
    return decision


def _infer_category(entry: dict) -> str:
    text = _clean(entry.get("text")).casefold()
    if "aura" in text or "has found" in text:
        return "aura"
    if "clip" in text:
        return "clip"
    if entry.get("biome") or "biome" in text or " rolled " in f" {text} ":
        return "biome"
    if any(word in text for word in ("disconnect", "reconnect", "window lost", "window found")):
        return "connection"
    if any(word in text for word in ("fish", "caught", "sell route", "sold ")):
        return "fishing"
    if "merchant" in text:
        return "merchant"
    if any(word in text for word in ("auto pop", "item used", "module", "failsafe", "eden")):
        return "action"
    return "system"


def _load_locked() -> None:
    global _loaded, _entries, _seq
    if _loaded:
        return
    _loaded = True
    try:
        raw = json.loads(_path().read_text(encoding="utf-8"))
        rows = raw.get("entries", []) if isinstance(raw, dict) else []
        if not isinstance(rows, list):
            return
        clean_rows = []
        for row in rows[-MAX_ENTRIES:]:
            if not isinstance(row, dict):
                continue
            try:
                event_id = int(row.get("id"))
                timestamp = float(row.get("ts"))
            except (TypeError, ValueError):
                continue
            text = _clean(row.get("text"))
            if not text:
                continue
            clean = {
                "id": event_id,
                "ts": timestamp,
                "text": text,
                "kind": _clean(row.get("kind"), 20) or "info",
                "category": _clean(row.get("category"), 30) or _infer_category(row),
                "account": _clean(row.get("account"), 80) or None,
                "accountId": row.get("accountId"),
            }
            try:
                if clean["accountId"] is not None:
                    clean["accountId"] = int(clean["accountId"])
            except (TypeError, ValueError):
                clean["accountId"] = None
            if row.get("biome"):
                clean["biome"] = _clean(row.get("biome"), 80)
            decision = _clean_decision(row.get("decision"))
            if decision:
                clean["decision"] = decision
            clean_rows.append(clean)
        _entries = clean_rows
        _seq = max((row["id"] for row in clean_rows), default=0)
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError):
        _entries = []
        _seq = 0


def _payload_locked() -> bytes:
    return json.dumps(
        {"version": 1, "entries": _entries},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def flush() -> None:
    global _save_timer
    with _lock:
        if not _loaded:
            return
        _load_locked()
        _save_timer = None
        target = _path()
        payload = _payload_locked()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except OSError as exc:
        print(f"[Timeline] Could not save account history: {exc}")


def _schedule_save_locked() -> None:
    global _save_timer
    if _save_timer is not None:
        return
    _save_timer = threading.Timer(0.75, flush)
    _save_timer.daemon = True
    _save_timer.start()


def record_activity(entry: dict) -> dict | None:
    
    global _seq
    if not isinstance(entry, dict):
        return None
    text = _clean(entry.get("text"))
    if not text:
        return None
    category = _clean(entry.get("category"), 30) or _infer_category(entry)
    kind = _clean(entry.get("kind"), 20) or "info"
    account = _clean(entry.get("account"), 80) or None


    if category == "system" and kind not in {"good", "bad", "warn"}:
        return None
    with _lock:
        _load_locked()
        _seq += 1
        row = {
            "id": _seq,
            "ts": float(entry.get("ts") or time.time()),
            "text": text,
            "kind": kind,
            "category": category,
            "account": account,
            "accountId": entry.get("accountId"),
        }
        if entry.get("biome"):
            row["biome"] = _clean(entry.get("biome"), 80)
        decision = _clean_decision(entry.get("decision"))
        if decision:
            row["decision"] = decision
        _entries.append(row)
        if len(_entries) > MAX_ENTRIES:
            del _entries[: len(_entries) - MAX_ENTRIES]
        _schedule_save_locked()
        return dict(row)


def get(account_id=None, before_id=None, limit=250, categories=None,
        search=None, kinds=None, since_ts=None) -> dict:
    try:
        limit = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        limit = 250
    try:
        account_filter = int(account_id) if account_id not in (None, "", "all") else None
    except (TypeError, ValueError):
        account_filter = None
    try:
        before_filter = int(before_id) if before_id not in (None, "") else None
    except (TypeError, ValueError):
        before_filter = None
    if isinstance(categories, str):
        wanted = {item.strip().casefold() for item in categories.split(",") if item.strip()}
    elif isinstance(categories, (list, tuple, set)):
        wanted = {str(item).strip().casefold() for item in categories if str(item).strip()}
    else:
        wanted = set()
    if isinstance(kinds, str):
        wanted_kinds = {item.strip().casefold() for item in kinds.split(",") if item.strip()}
    elif isinstance(kinds, (list, tuple, set)):
        wanted_kinds = {str(item).strip().casefold() for item in kinds if str(item).strip()}
    else:
        wanted_kinds = set()
    query_parts = [part for part in _clean(search, 120).casefold().split() if part]
    try:
        since_filter = float(since_ts) if since_ts not in (None, "") else None
    except (TypeError, ValueError):
        since_filter = None

    def matches_search(row):
        if not query_parts:
            return True
        haystack = " ".join(str(row.get(key) or "") for key in (
            "text", "account", "category", "biome", "kind"
        )).casefold()
        if row.get("decision"):
            haystack += " " + json.dumps(row["decision"], ensure_ascii=False).casefold()
        return all(part in haystack for part in query_parts)

    with _lock:
        _load_locked()
        matched = [
            row for row in reversed(_entries)
            if (account_filter is None or row.get("accountId") == account_filter)
            and (before_filter is None or row["id"] < before_filter)
            and (
                not wanted
                or row.get("category") in wanted
                or ("issues" in wanted and row.get("kind") in {"bad", "warn"})
            )
            and (not wanted_kinds or row.get("kind") in wanted_kinds)
            and (since_filter is None or row.get("ts", 0) >= since_filter)
            and matches_search(row)
        ]
        return {
            "entries": [dict(row) for row in matched[:limit]],
            "hasMore": len(matched) > limit,
            "total": len(matched),
        }


def clear(account_id=None) -> dict:
    global _entries
    try:
        account_filter = int(account_id) if account_id not in (None, "", "all") else None
    except (TypeError, ValueError):
        account_filter = None
    with _lock:
        _load_locked()
        before = len(_entries)
        if account_filter is None:
            _entries = []
        else:
            _entries = [row for row in _entries if row.get("accountId") != account_filter]
        removed = before - len(_entries)
    flush()
    return {"ok": True, "removed": removed}


def _reset_for_tests(path=None) -> None:
    
    global _entries, _seq, _loaded, _save_timer, _path_override
    with _lock:
        if _save_timer is not None:
            _save_timer.cancel()
        _save_timer = None
        _entries = []
        _seq = 0
        _loaded = False
        _path_override = Path(path) if path else None


atexit.register(flush)
