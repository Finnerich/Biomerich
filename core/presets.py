PIXEL_SLOTS = [
    ("inventory_button", "Inventory Button"),
    ("item_tab",         "Item Tab"),
    ("search_bar",       "Search Bar"),
    ("first_item_slot",  "First Item Slot"),
    ("amount_box",       "Amount Box"),
    ("use_button",       "Use Button"),
]

PRESETS = {
    "1920x1080 WINDOWED (100%)": {
        "inventory_button": [35, 506],
        "item_tab": [1267, 328],
        "search_bar": [808, 354],
        "first_item_slot": [850, 471],
        "amount_box": [566, 563],
        "use_button": [681, 565],
    },
    "1920x1080 FULLSCREEN (100%)": {
        "inventory_button": [33, 511],
        "item_tab": [1269, 335],
        "search_bar": [810, 367],
        "first_item_slot": [849, 475],
        "amount_box": [580, 577],
        "use_button": [686, 576],
    },
}

def slot_keys():
    return [key for key, _label in PIXEL_SLOTS]

def slot_label(key):
    for k, label in PIXEL_SLOTS:
        if k == key:
            return label
    return key

def preset_names():
    return list(PRESETS.keys())

def get_preset(name):
    data = PRESETS.get(name)
    if not data:
        return None
    out = {}
    for key in slot_keys():
        pos = data.get(key)
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            out[key] = [int(pos[0]), int(pos[1])]
    return out
