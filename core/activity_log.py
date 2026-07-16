

import time
import threading
from collections import deque

_lock = threading.Lock()
_entries = deque(maxlen=500)
_seq = 0




account_provider = None


def push(text, account=None, kind="info", biome=None):
    global _seq
    if not text:
        return
    if account is None and account_provider is not None:
        try:
            account = account_provider() or None
        except Exception:
            account = None
    with _lock:
        _seq += 1
        entry = {"id": _seq, "ts": time.time(), "text": str(text), "kind": kind,
                 "account": account}
        if biome:
            entry["biome"] = biome
        _entries.append(entry)


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
