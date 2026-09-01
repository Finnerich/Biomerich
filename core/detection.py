

import re

from . import merchants_data




def norm_name(s):
    
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match_reads(mid, reads):
    
    totals = {}
    for txt in reads:
        head = txt.split("|")[0].strip()
        for cand_txt in {txt, head}:
            if not cand_txt:
                continue
            name, sc = merchants_data.match_autobuy_item(mid, cand_txt)
            if name:
                totals[name] = totals.get(name, 0.0) + sc
    if not totals:
        return None, 0.0
    name, score = max(totals.items(), key=lambda kv: (kv[1], len(kv[0])))
    return name, score


def parse_stock_text(text, confident_only=False):
    
    if not text:
        return None
    s = str(text)
    m = re.search(r"(?:left|eft|lett|1eft)\s*[:;.,]*\s*([0-9OoIl|]+)", s, re.IGNORECASE)
    token = m.group(1) if m else None
    if token is None:
        if confident_only:
            return None
        nums = re.findall(r"(?<![A-Za-z0-9])\d+(?![A-Za-z0-9])", s)
        token = nums[-1] if nums else None
    if token is None:
        return None
    token = (token.replace("O", "0").replace("o", "0")
                  .replace("I", "1").replace("l", "1").replace("|", "1"))
    try:
        return int(token)
    except ValueError:
        return None
