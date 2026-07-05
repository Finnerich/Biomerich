


def armed_autobuy_items(entry):
    
    if not entry or not entry.get("enabled"):
        return {}
    out = {}
    for it in entry.get("items", []):
        name = str(it.get("name") or "").strip()
        buy_all = bool(it.get("all"))
        try:
            amt = int(it.get("amount", 0))
        except (TypeError, ValueError):
            amt = 0
        if name and (buy_all or amt > 0):
            out[name] = {"amount": amt, "all": buy_all}
    return out


def buy_plan(stock, want, buy_all):
    
    if buy_all or stock <= want:
        return True, stock
    return False, want
