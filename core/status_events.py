

import time
import threading

from . import activity_log

_lock = threading.Lock()

_event = None
_event_seq = 0

_detail = None

def push_event(text, kind="info", ttl=2.0, account=None, account_id=None,
               category=None, decision=None):
    
    global _event, _event_seq
    if not text:
        return
    activity_log.push(
        text, kind=kind, account=account, account_id=account_id,
        category=category, decision=decision,
    )
    with _lock:
        _event_seq += 1
        _event = {
            "text": str(text),
            "kind": kind,
            "expires": None if ttl is None else time.time() + max(0.5, float(ttl)),
            "id": _event_seq,
        }

def clear_event():
    
    global _event
    with _lock:
        _event = None

def set_detail(text, restart=True):
    
    global _detail
    with _lock:
        if (not restart and _detail is not None
                and _detail.get("text") == str(text)):
            return
        _detail = {"text": str(text), "since": time.time()}

def clear_detail():
    global _detail
    with _lock:
        _detail = None

def reset():
    global _event, _detail
    with _lock:
        _event = None
        _detail = None

def snapshot():
    
    now = time.time()
    with _lock:
        out = {}
        if _event is not None:
            if _event["expires"] is None or _event["expires"] >= now:
                out["event"] = {
                    "text": _event["text"],
                    "kind": _event["kind"],
                    "id": _event["id"],
                    "remaining": None if _event["expires"] is None
                                 else round(_event["expires"] - now, 2),
                }
        if _detail is not None:
            out["detail"] = {
                "text": _detail["text"],
                "elapsed": int(now - _detail["since"]),
            }
        return out
