import os
import re
import sys
import tempfile
from difflib import SequenceMatcher

from . import win_pixel

IS_WINDOWS = sys.platform == "win32"

_pytesseract = None
_Image       = None
_checked     = False
_available   = False
_last_error  = ""

def _resolve_tesseract_cmd():
    env = os.getenv("SOLRICH_TESSERACT") or os.getenv("BIOMERICH_TESSERACT")
    if env and os.path.exists(env):
        return env
    try:
        from .tesseract_install import find_tesseract
        return find_tesseract()
    except Exception:
        return None

def _ensure():
    global _pytesseract, _Image, _checked, _available, _last_error
    if _checked:
        return _available
    _checked = True
    try:
        import pytesseract
        from PIL import Image
    except Exception as e:
        _last_error = f"missing dependency: {e}"
        _available  = False
        return False
    cmd = _resolve_tesseract_cmd()
    if cmd:
        try:
            pytesseract.pytesseract.tesseract_cmd = cmd
            tessdata = os.path.join(os.path.dirname(cmd), "tessdata")
            if os.path.isdir(tessdata):
                os.environ.setdefault("TESSDATA_PREFIX", tessdata)
        except Exception:
            pass
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        _last_error = f"tesseract binary not found: {e}"
        _available  = False
        return False
    _pytesseract = pytesseract
    _Image       = Image
    _available   = True
    _last_error  = ""
    return True

def available():
    return _ensure()

def reset_cache():
    
    global _checked, _available, _last_error
    _checked = False
    _available = False
    _last_error = ""

def status():
    ok = _ensure()
    return {"available": ok, "error": _last_error}

def _image_from_region(x, y, w, h):
    if not IS_WINDOWS:
        return None
    gw, gh, data = win_pixel.grab_region(x, y, w, h)
    if not data or gw <= 0 or gh <= 0:
        return None
    try:
        return _Image.frombytes("RGBA", (gw, gh), data, "raw", "BGRA")
    except Exception:
        return None

def _prep(img, scale, threshold, invert):
    img = img.convert("L")
    if scale and scale > 1:
        img = img.resize(
            (img.width * scale, img.height * scale), _Image.LANCZOS
        )
    if threshold is not None:
        t = int(threshold)
        img = img.point(lambda p: 255 if p > t else 0)
    if invert:
        img = img.point(lambda p: 255 - p)
    return img

def _prep_max(img, scale, threshold, invert):
    
    from PIL import ImageChops
    r, g, b = img.convert("RGB").split()
    m = ImageChops.lighter(ImageChops.lighter(r, g), b)
    if scale and scale > 1:
        m = m.resize((m.width * scale, m.height * scale), _Image.LANCZOS)
    if threshold is not None:
        t = int(threshold)
        m = m.point(lambda p: 255 if p > t else 0)
    if invert:
        m = m.point(lambda p: 255 - p)
    return m

def _read_img(img, psm):

    cfg = f"--psm {int(psm)} --oem 3"
    text = _pytesseract.image_to_string(img, config=cfg)
    return (text or "").strip()

def read_region_variants(x, y, w, h, color_boost=False, stop_when=None):
    
    if not _ensure():
        return []

    img = _image_from_region(x, y, w, h)
    if img is None:
        return []

    combos = [
        (3, None,  False, 7),
        (3, None,  True,  7),
        (3, 100,   False, 7),
        (3, 100,   True,  7),
        (3, 160,   False, 7),
        (3, 160,   True,  7),
        (3, None,  False, 6),
        (3, None,  True,  6),
        (3, 100,   False, 6),
        (3, 100,   True,  6),
    ]
    boost_combos = [
        (4, 60,   True,  7),
        (4, 110,  True,  7),
        (4, None, True,  7),
        (4, 60,   True,  6),
        (3, 80,   True,  7),
        (3, 150,  True,  7),
    ]

    seen = set()
    out  = []

    def _try(prep_fn, scale, thr, inv, psm):
        
        try:
            txt = _read_img(prep_fn(img.copy(), scale, thr, inv), psm)
            if txt and txt not in seen:
                seen.add(txt)
                out.append(txt)
                if stop_when is not None and stop_when(txt):
                    return True
        except Exception:
            pass
        return False

    if color_boost:
        for scale, thr, inv, psm in boost_combos:
            if _try(_prep_max, scale, thr, inv, psm):
                return out
    for scale, thr, inv, psm in combos:
        if _try(_prep, scale, thr, inv, psm):
            return out
    return out

def normalize(s):
    s = (s or "").lower()

    s = s.replace("0", "o").replace("1", "l").replace("|", "l")
    s = s.replace("4", "a").replace("@", "a")

    s = re.sub(r"[^a-z ]", "", s)
    s = re.sub(r" +", " ", s).strip()
    return s

def similarity(a, b):
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0

    shorter = na if len(na) <= len(nb) else nb
    if len(shorter) >= 4 and (na in nb or nb in na):
        return 0.92
    return SequenceMatcher(None, na, nb).ratio()

def region_matches(x, y, w, h, target, threshold=0.62):
    if not _ensure():
        return (None, "", 0.0)
    best = {"text": "", "score": 0.0}
    def _score_and_stop(txt):
        score = similarity(txt, target)
        if score > best["score"]:
            best["text"], best["score"] = txt, score
        return best["score"] >= threshold
    read_region_variants(x, y, w, h, stop_when=_score_and_stop)
    return (best["score"] >= threshold, best["text"], best["score"])

def save_debug_image(x, y, w, h, path=None):

    if not _ensure():
        return None
    img = _image_from_region(x, y, w, h)
    if img is None:
        return None
    if path is None:
        fd, path = tempfile.mkstemp(suffix="_ocr_debug.png")
        os.close(fd)
    try:
        img.save(path)
        return path
    except Exception:
        return None
