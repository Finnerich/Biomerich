

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


def _component_text(message: dict) -> list:
    texts = []

    def walk(component):
        if not isinstance(component, dict):
            return
        if component.get("type") == 10 and component.get("content"):
            texts.append(component["content"])
        for child in component.get("components", []) or []:
            walk(child)

    for component in message.get("components", []) or []:
        walk(component)
    return texts


def _component_color(message: dict):
    for component in message.get("components", []) or []:
        if component.get("type") == 17:
            return component.get("accent_color")
    return None


def maybe_log(message, image_bytes=None, account=None) -> None:
    
    global _seq, _last_desc, _last_ts
    if not isinstance(message, dict):
        return
    desc = message.get("description", "") or "\n".join(_component_text(message))
    now = time.time()
    with _lock:
        if desc and desc == _last_desc and (now - _last_ts) < 2.5:
            return
        _last_desc, _last_ts = desc, now
        raw_lines = [line for line in desc.splitlines() if line.strip()]
        title_index = next(
            (i for i, line in enumerate(raw_lines) if line.lstrip().startswith("#")),
            0,
        )
        lines = [_clean(line) for line in raw_lines[title_index:]]
        lines = [
            line for line in lines
            if line
            and "support server" not in line.lower()
            and "join server" not in line.lower()
            and not line.lower().startswith("solrich v")
            and not line.startswith("<t:")
        ]
        title = lines[0] if lines else "Event"
        detail = " · ".join(lines[1:5])
        if isinstance(account, dict):
            account_name = account.get("name") or ""
        else:
            account_name = account or ((message.get("author") or {}).get("name")) or ""
        _seq += 1
        _log.append({
            "id": _seq,
            "kind": _kind_from(title),
            "account": account_name,
            "title": title,
            "detail": detail,
            "color": message.get("color", _component_color(message)),
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
