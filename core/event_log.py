

import base64
import io
import re
import threading
import time

_lock = threading.Lock()
_log: list = []
_seq = 0
_MAX = 150
_last_desc = ""
_last_ts = 0.0


def _kind_from(title: str) -> str:
    t = (title or "").lower()
    if "eden" in t or "devourer" in t:
        return "eden"
    if "aura" in t:
        return "aura"
    if "auto buy" in t:
        return "autobuy"
    if "auto pop" in t:
        return "autopop"
    if "merchant" in t:
        return "merchant"
    if "biome" in t:
        return "biome"
    if "fish" in t or "sell route" in t:
        return "fishing"
    if any(w in t for w in ("failsafe", "fake rare", "disconnect", "triggered", "failed", "blocked")):
        return "failsafe"
    return "system"


def _clean(s: str) -> str:
    return re.sub(r"[#>*_`]+", "", s or "").strip()


def _downscale(raw: bytes):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.width > 480:
            r = 480 / im.width
            im = im.resize((480, max(1, int(im.height * r))))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=55)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def maybe_log(embed, image_bytes=None) -> None:
    
    global _seq, _last_desc, _last_ts
    if not isinstance(embed, dict):
        return
    desc = embed.get("description", "") or ""
    now = time.time()
    with _lock:
        if desc and desc == _last_desc and (now - _last_ts) < 2.5:
            return
        _last_desc, _last_ts = desc, now
        lines = [l for l in _clean(desc).splitlines() if l.strip()]
        lines = [l for l in lines if "support server" not in l.lower() and "join server" not in l.lower()]
        title = lines[0] if lines else "Event"
        detail = " · ".join(lines[1:5])
        account = ((embed.get("author") or {}).get("name")) or ""
        _seq += 1
        _log.append({
            "id": _seq,
            "kind": _kind_from(title),
            "account": account,
            "title": title,
            "detail": detail,
            "color": embed.get("color"),
            "image": _downscale(image_bytes) if image_bytes else None,
            "ts": now,
        })
        if len(_log) > _MAX:
            del _log[: len(_log) - _MAX]


def get(since_id=0) -> list:
    with _lock:
        try:
            since_id = int(since_id or 0)
        except (TypeError, ValueError):
            since_id = 0
        return [dict(e) for e in _log if e["id"] > since_id]
