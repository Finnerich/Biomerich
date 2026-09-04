PIXEL_SLOTS = [
    ("inventory_button", "Inventory Button"),
    ("item_tab",         "Item Tab"),
    ("search_bar",       "Search Bar"),
    ("first_item_slot",  "First Item Slot"),
    ("amount_box",       "Amount Box"),
    ("use_button",       "Use Button"),
]

PRESETS = {
    "[1080p] WINDOWED 1920x1080 (100%)": {
        "inventory_button": [35, 506],
        "item_tab": [1267, 328],
        "search_bar": [808, 354],
        "first_item_slot": [847, 462],
        "amount_box": [566, 563],
        "use_button": [681, 565],
        "first_item_region": [800, 418, 94, 89],
        "autopop_amount_region": [848, 482, 42, 21],
    },
    "[1080p] FULLSCREEN 1920x1080 (100%)": {
        "inventory_button": [33, 511],
        "item_tab": [1269, 335],
        "search_bar": [810, 367],
        "first_item_slot": [848, 476],
        "amount_box": [580, 577],
        "use_button": [686, 576],
        "first_item_region": [804, 432, 88, 88],
        "autopop_amount_region": [855, 495, 35, 24],
    },
    "[WUXGA] WINDOWED 1920x1200 (125%)": {
        "inventory_button": [35, 572],
        "item_tab": [1270, 395],
        "search_bar": [813, 426],
        "first_item_slot": [847, 534],
        "amount_box": [566, 634],
        "use_button": [683, 639],
        "first_item_region": [804, 492, 88, 85],
        "autopop_amount_region": [847, 555, 43, 21],
    },
    "[UWQHD] WINDOWED 3440x1440 (150%)": {
        "inventory_button": [60, 673],
        "item_tab": [2192, 415],
        "search_bar": [1497, 463],
        "first_item_slot": [1553, 624],
        "amount_box": [1127, 781],
        "use_button": [1306, 778],
        "first_item_region": [1486, 558, 135, 132],
        "autopop_amount_region": [1546, 651, 70, 35],
    },
    "[4K] WINDOWED 3840x2160 (150%)": {
        "inventory_button": [63, 1007],
        "item_tab": [2550, 656],
        "search_bar": [1647, 714],
        "amount_box": [1134, 1132],
        "use_button": [1362, 1142],
    },
    "[4K] FULLSCREEN 3840x2160 (150%)": {
        "inventory_button": [60, 1026],
        "item_tab": [2547, 671],
        "search_bar": [1626, 737],
        "amount_box": [1136, 1153],
        "use_button": [1355, 1161],
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

def get_preset_regions(name):
    
    data = PRESETS.get(name)
    if not data:
        return {}
    out = {}
    for key in ("first_item_region", "autopop_amount_region"):
        box = data.get(key)
        if isinstance(box, (list, tuple)) and len(box) == 4:
            out[key] = [int(v) for v in box]
    return out
