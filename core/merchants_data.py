MERCHANT_PIXEL_SLOTS = [
    ("dialogue_skip", "Dialogue Skip"),
    ("open_merchant", "Open Merchant Button"),
    ("item_slot_1", "Item Slot 1"),
    ("item_slot_2", "Item Slot 2"),
    ("item_slot_3", "Item Slot 3"),
    ("item_slot_4", "Item Slot 4"),
    ("item_slot_5", "Item Slot 5"),
    ("amount_box", "Amount Box"),
    ("set_max_button", "Set To Max Button"),
    ("buy_button", "Buy Button"),
]

MERCHANT_REGIONS = [
    ("merchant_name", "Merchant Name (dialog)"),
    ("loading_screen", "Loading Screen Marker"),
]

ITEM_SLOT_KEYS = [s for s, _ in MERCHANT_PIXEL_SLOTS if s.startswith("item_slot_")]

MERCHANT_CALIB_GROUPS = [
    {
        "key": "general",
        "label": "Merchant General",
        "scope": "Shared by every merchant",
        "points": [
            ("dialogue_skip", "Dialogue Skip"),
        ],
        "regions": [
            ("merchant_name", "Merchant Name"),
        ],
    },
    {
        "key": "shop",
        "label": "Merchant Shop",
        "scope": "Shared buy panel",
        "points": [
            ("buy_button", "Buy Button"),
            ("amount_box", "Amount Box"),
            ("set_max_button", "Set To Max Button"),
            ("close_button", "Close Button"),
        ],
        "regions": [
            ("item_slot_1", "Item Slot 1"),
            ("item_slot_2", "Item Slot 2"),
            ("item_slot_3", "Item Slot 3"),
            ("item_slot_4", "Item Slot 4"),
            ("item_slot_5", "Item Slot 5"),
            ("amount_label", "Amount Label"),
            ("item_name", "Item Name (optional)"),
        ],
    },
    {
        "key": "mari",
        "label": "Mari Dialogue",
        "scope": "Mari only",
        "points": [
            ("open_button", "Open Button"),
            ("leave_button", "Leave Button"),
        ],
        "regions": [],
    },
    {
        "key": "jester",
        "label": "Jester Dialogue",
        "scope": "Jester only",
        "points": [
            ("open_button", "Open Button"),
            ("exchange_button", "Exchange Button"),
            ("leave_button", "Leave Button"),
        ],
        "regions": [],
    },
    {
        "key": "rin",
        "label": "Rin Dialogue",
        "scope": "Rin only",
        "points": [
            ("leave_button", "Leave Button"),
        ],
        "regions": [],
    },
]

DETECTABLE_MERCHANTS = {
    "mari": "Mari",
    "jester": "Jester",
    "rin": "Rin",
}

DETECT_MATCH_THRESHOLD = 0.6

AUTOBUY_MERCHANTS = ("mari", "jester")

AUTOBUY_ITEMS = {
    "mari": [
        "Void Coin",
        "Gear A",
        "Gear B",
        "Lucky Penny",
        "Fortune Spoid I",
        "Fortune Spoid II",
        "Fortune Spoid III",
        "Mixed Potion",
        "Lucky Potion",
        "Lucky Potion L",
        "Lucky Potion XL",
        "Speed Potion",
        "Speed Potion L",
        "Speed Potion XL",
    ],
    "jester": [
        "Oblivion Potion",
        "Heavenly Potion",
        "Potion of Bound",
        "Strange Potion I",
        "Strange Potion II",
        "Lucky Potion",
        "Speed Potion",
        "Rune of Everything",
        "Rune of Nothing",
        "Rune of Corruption",
        "Rune of Galaxy",
        "Rune of Hell",
        "Rune of Rainstorm",
        "Rune of Frost",
        "Rune of Wind",
        "Stella's Star",
        "Merchant Tracker",
        "Random Potion Sack",
    ],
}

AUTOBUY_MATCH_THRESHOLD = 0.62

def required_shop_region_keys():
    
    return [k for k in calib_region_keys("shop") if k != "item_name"]

def autobuy_items(mid):
    return list(AUTOBUY_ITEMS.get(mid, []))

def match_autobuy_item(mid, text):
    
    from . import ocr
    buyable = AUTOBUY_ITEMS.get(mid, [])
    catalog = list(dict.fromkeys(list(buyable) + item_names(mid)))
    best, best_score = None, 0.0
    for name in catalog:
        score = ocr.similarity(text, name)
        if score > best_score or (
            best is not None and score == best_score and score > 0.0
            and len(name) > len(best)
        ):
            best, best_score = name, score
    if best and best_score >= AUTOBUY_MATCH_THRESHOLD and best in buyable:
        return best, best_score
    return None, best_score

def calib_groups():
    return MERCHANT_CALIB_GROUPS

def calib_group_keys():
    return [g["key"] for g in MERCHANT_CALIB_GROUPS]

def calib_group(key):
    for g in MERCHANT_CALIB_GROUPS:
        if g["key"] == key:
            return g
    return None

def calib_point_keys(group_key):
    g = calib_group(group_key)
    return [k for k, _ in (g.get("points") if g else [])]

def calib_region_keys(group_key):
    g = calib_group(group_key)
    return [k for k, _ in (g.get("regions") if g else [])]

def calib_label(group_key, slot):
    g = calib_group(group_key)
    if not g:
        return slot
    for k, lbl in g.get("points", []):
        if k == slot:
            return lbl
    for k, lbl in g.get("regions", []):
        if k == slot:
            return lbl
    return slot

def detect_merchant_id(text):
    
    from . import ocr
    best_id, best_score = None, 0.0
    for mid, name in DETECTABLE_MERCHANTS.items():
        score = ocr.similarity(text, name)
        if score > best_score:
            best_id, best_score = mid, score
    if best_score >= DETECT_MATCH_THRESHOLD:
        return best_id, best_score
    return None, best_score

def detect_merchant_name(mid):
    return DETECTABLE_MERCHANTS.get(mid, mid)

MERCHANTS = {
    "jester": {
        "id": "jester",
        "name": "Jester",
        "currency": "P",
        "items": [
            {"name": "Lucky Potion", "price": "1P", "maxStock": 45},
            {"name": "Speed Potion", "price": "2P", "maxStock": 45},
            {"name": "Random Potion Sack", "price": "10P", "maxStock": 10},
            {"name": "Stella's Star", "price": "5P", "maxStock": 1},
            {"name": "Rune of Wind", "price": "50P", "maxStock": 1},
            {"name": "Rune of Frost", "price": "50P", "maxStock": 1},
            {"name": "Rune of Rainstorm", "price": "50P", "maxStock": 1},
            {"name": "Rune of Hell", "price": "300P", "maxStock": 1},
            {"name": "Rune of Galaxy", "price": "375P", "maxStock": 1},
            {"name": "Rune of Corruption", "price": "450P", "maxStock": 1},
            {"name": "Rune of Nothing", "price": "650P", "maxStock": 1},
            {"name": "Rune of Everything", "price": "3000P", "maxStock": 1},
            {"name": "Strange Potion I", "price": "15P", "maxStock": 25},
            {"name": "Strange Potion II", "price": "25P", "maxStock": 25},
            {"name": "Stella's Candle", "price": "50P", "maxStock": 5},
            {"name": "Oblivion Potion", "price": "5 Void Coins", "maxStock": 1},
            {"name": "Potion of Bound", "price": "500P", "maxStock": 1},
            {"name": "Merchant Tracker", "price": "1000P", "maxStock": 1},
            {"name": "Heavenly Potion", "price": "1000P", "maxStock": 1},
        ],
    },
    "mari": {
        "id": "mari",
        "name": "Mari",
        "currency": "$",
        "items": [
            {"name": "Lucky Potion", "price": "1,000$", "maxStock": 25},
            {"name": "Lucky Potion L", "price": "2,000$", "maxStock": 10},
            {"name": "Lucky Potion XL", "price": "4,000$", "maxStock": 5},
            {"name": "Speed Potion", "price": "2,000$", "maxStock": 25},
            {"name": "Speed Potion L", "price": "4,000$", "maxStock": 10},
            {"name": "Speed Potion XL", "price": "8,000$", "maxStock": 10},
            {"name": "Mixed Potion", "price": "3,000$", "maxStock": 25},
            {"name": "Fortune Spoid I", "price": "4,000$", "maxStock": 4},
            {"name": "Fortune Spoid II", "price": "6,000$", "maxStock": 4},
            {"name": "Fortune Spoid III", "price": "8,000$", "maxStock": 1},
            {"name": "Gear A", "price": "10,000$", "maxStock": 1},
            {"name": "Gear B", "price": "10,000$", "maxStock": 1},
            {"name": "Rainbow Syrup", "price": "3,000$", "maxStock": 0},
            {"name": "Lucky Penny", "price": "77,777$", "maxStock": 3},
            {"name": "Void Coin", "price": "500,000$", "maxStock": 2},
        ],
    },
}

MERCHANT_ORDER = ["mari", "jester"]

def merchant_ids():
    return list(MERCHANT_ORDER)

def get_merchant(mid):
    return MERCHANTS.get(mid)

def merchant_name(mid):
    m = MERCHANTS.get(mid)
    return m["name"] if m else mid

def item_names(mid):
    m = MERCHANTS.get(mid)
    return [i["name"] for i in m["items"]] if m else []

def all_item_names():
    seen, out = set(), []
    for mid in MERCHANT_ORDER:
        for n in item_names(mid):
            if n not in seen:
                seen.add(n)
                out.append(n)
    return out

def item_max_stock(mid, name):
    m = MERCHANTS.get(mid)
    if not m:
        return 1
    for it in m["items"]:
        if it["name"] == name:
            return int(it.get("maxStock", 1))
    return 1

def merchant_id_from_name(text):

    from . import ocr
    best_id, best_score = None, 0.0
    for mid, m in MERCHANTS.items():
        score = ocr.similarity(text, m["name"])
        if score > best_score:
            best_id, best_score = mid, score
    if best_score >= 0.7:
        return best_id
    return None

def pixel_slot_keys():
    return [k for k, _ in MERCHANT_PIXEL_SLOTS]

def region_keys():
    return [k for k, _ in MERCHANT_REGIONS]
