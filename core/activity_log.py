

import time
import threading
from collections import deque

_lock = threading.Lock()
_entries = deque(maxlen=500)
_seq = 0




account_provider = None
account_id_provider = None
timeline_sink = None


def push(text, account=None, kind="info", biome=None, account_id=None,
         category=None, persist=True, decision=None):
    global _seq
    if not text:
        return
    if account is None and account_provider is not None:
        try:
            account = account_provider() or None
        except Exception:
            account = None
    if account_id is None and account and account_id_provider is not None:
        try:
            account_id = account_id_provider(account)
        except Exception:
            account_id = None
    with _lock:
        _seq += 1
        entry = {"id": _seq, "ts": time.time(), "text": str(text), "kind": kind,
                 "account": account}
        if account_id is not None:
            entry["accountId"] = account_id
        if biome:
            entry["biome"] = biome
        if category:
            entry["category"] = category
        if decision:
            entry["decision"] = decision
        _entries.append(entry)
    if persist and timeline_sink is not None:
        try:
            timeline_sink(dict(entry))
        except Exception as exc:
            print(f"[Timeline] Could not record activity: {exc}")


def since(since_id=0):
    try:
        since_id = int(since_id)
    except (TypeError, ValueError):
        since_id = 0
    with _lock:
        out = [e for e in _entries if e["id"] > since_id]
        return {"entries": out, "last": _seq}


def reset():
    
    with _lock:
        _entries.clear()
