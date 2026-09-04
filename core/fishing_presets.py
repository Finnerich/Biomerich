PIXEL_SLOTS = [
    ("cast_point", "Start Fishing Button"),
    ("bite_indicator", "Fish Indicator Pixel"),
    ("bar_sample", "Mid Bar Color Sample"),
    ("zone_left", "Bar Region Left"),
    ("zone_right", "Bar Region Right"),
    ("reel_click", "Reel Click Spot"),
    ("claim_button", "Close / Claim Button"),
    ("collection_button", "Collection Button"),
    ("collection_close_button", "Collection Close Button"),
    ("fish_dialogue", "Shop Dialogue"),
    ("sell_fish_button", "Sell Fish Button"),
    ("first_fish_slot", "First Fish Slot"),
    ("sell_all_button", "Sell All Button"),
    ("sell_confirm_button", "Sell Confirm Button"),
    ("fish_shop_close_button", "Shop Close Button"),
]

REGION_SLOTS = [
    ("fishing_failed", "Fishing Failed / Caught Text"),
    ("shop_name", "Shop Name (Captain Flarg)"),
]

PRESETS = {
    "[1080p] WINDOWED 1920x1080 (100%)": {
        "cast_point": [848, 801],
        "bite_indicator": [1176, 801],
        "bar_sample": [948, 731],
        "zone_left": [759, 747],
        "zone_right": [1159, 729],
        "reel_click": [961, 859],
        "claim_button": [1110, 333],
        "collection_button": [33, 449],
        "collection_close_button": [384, 146],
        "fish_dialogue": [970, 797],
        "sell_fish_button": [963, 901],
        "first_fish_slot": [831, 405],
        "sell_all_button": [665, 777],
        "sell_confirm_button": [801, 616],
        "fish_shop_close_button": [1460, 271],
        "fishing_failed": [790, 315, 309, 55],
        "shop_name": [751, 671, 208, 38],
    },
    "[1080p] FULLSCREEN 1920x1080 (100%)": {
        "cast_point": [850, 835],
        "bite_indicator": [1175, 836],
        "bar_sample": [955, 763],
        "zone_left": [759, 778],
        "zone_right": [1164, 754],
        "reel_click": [963, 911],
        "claim_button": [1110, 340],
        "collection_button": [33, 461],
        "collection_close_button": [386, 126],
        "fish_dialogue": [964, 817],
        "sell_fish_button": [966, 943],
        "first_fish_slot": [833, 396],
        "sell_all_button": [671, 803],
        "sell_confirm_button": [800, 618],
        "fish_shop_close_button": [1460, 266],
        "fishing_failed": [783, 318, 354, 61],
        "shop_name": [726, 684, 245, 54],
    },
    "[WUXGA] WINDOWED 1920x1200 (125%)": {
        "cast_point": [834, 930],
        "bite_indicator": [1199, 930],
        "bar_sample": [941, 850],
        "zone_left": [735, 869],
        "zone_right": [1183, 846],
        "reel_click": [948, 957],
        "claim_button": [1141, 364],
        "collection_button": [35, 519],
        "collection_close_button": [383, 146],
        "fish_dialogue": [967, 911],
        "sell_fish_button": [962, 1037],
        "first_fish_slot": [831, 447],
        "sell_all_button": [664, 890],
        "sell_confirm_button": [805, 679],
        "fish_shop_close_button": [1457, 295],
        "fishing_failed": [752, 338, 369, 78],
        "shop_name": [711, 772, 249, 42],
    },
    "[UWQHD] WINDOWED 3440x1440 (150%)": {
        "cast_point": [1510, 1045],
        "bite_indicator": [2078, 1058],
        "bar_sample": [1699, 940],
        "zone_left": [1386, 966],
        "zone_right": [2054, 934],
        "reel_click": [1714, 1120],
        "claim_button": [1931, 428],
        "collection_button": [62, 576],
        "collection_close_button": [690, 201],
        "fish_dialogue": [1753, 1049],
        "sell_fish_button": [1713, 1189],
        "first_fish_slot": [1477, 570],
        "sell_all_button": [1191, 1018],
        "sell_confirm_button": [1461, 828],
        "fish_shop_close_button": [2627, 363],
        "fishing_failed": [1477, 411, 469, 70],
        "shop_name": [1438, 897, 271, 48],
    },
    "[WUXGA] FULLSCREEN 1920x1200 (100%)": {
        "cast_point": [848, 927],
        "bite_indicator": [1176, 929],
        "bar_sample": [936, 859],
        "zone_left": [758, 878],
        "zone_right": [1165, 854],
        "reel_click": [958, 1025],
        "claim_button": [1120, 389],
        "collection_button": [32, 515],
        "collection_close_button": [387, 134],
        "fish_dialogue": [758, 939],
        "sell_fish_button": [958, 1037],
        "first_fish_slot": [828, 439],
        "sell_all_button": [664, 888],
        "sell_confirm_button": [798, 685],
        "fish_shop_close_button": [1455, 297],
    },
    "[4K] WINDOWED 3840x2160 (150%)": {
        "cast_point": [1723, 1619],
        "bite_indicator": [2301, 1627],
        "bar_sample": [1908, 1499],
        "zone_left": [1564, 1528],
        "zone_right": [2273, 1499],
        "reel_click": [1931, 1697],
        "claim_button": [2180, 729],
        "collection_button": [65, 907],
        "collection_close_button": [777, 261],
        "fish_dialogue": [1974, 1599],
        "sell_fish_button": [1929, 1832],
        "first_fish_slot": [1659, 814],
        "sell_all_button": [1332, 1565],
        "sell_confirm_button": [1608, 1246],
        "fish_shop_close_button": [2921, 541],
    },
    "[4K] FULLSCREEN 3840x2160 (150%)": {
        "cast_point": [1729, 1676],
        "bite_indicator": [2303, 1679],
        "bar_sample": [1911, 1550],
        "zone_left": [1565, 1580],
        "zone_right": [2274, 1549],
        "reel_click": [1918, 1737],
        "claim_button": [2184, 735],
        "collection_button": [60, 911],
        "collection_close_button": [774, 226],
        "fish_dialogue": [1957, 1649],
        "sell_fish_button": [1929, 1889],
        "first_fish_slot": [1654, 822],
        "sell_all_button": [1340, 1606],
        "sell_confirm_button": [1606, 1254],
        "fish_shop_close_button": [2921, 534],
    },
}

RESET_AND_COLLECTION = [
    {"tap": "esc"},
    {"wait": 0.5, "slow_extra": 1.5},
    {"tap": "r"},
    {"wait": 0.5, "slow_extra": 1.5},
    {"tap": "enter"},
    {"wait": 2.75, "slow_extra": 2.0},
    {"click_slot": "collection_button"},
    {"wait": 0.25},
    {"click_slot": "collection_close_button"},
    {"wait": 0.25},
]

_RESET_AND_ZOOM = RESET_AND_COLLECTION + [
    {"scroll": 80},
    {"wait": 0.25},
    {"scroll": -15},
    {"wait": 0.25},
]

_SELL_SHOP_OPEN = [
    {"click_slot": "fish_dialogue", "shop_step": True},
    {"wait": 0.075, "shop_step": True},
    {"shop_name_check": True},
    {"click_slot": "sell_fish_button", "shop_step": True},
    {"wait": 0.15, "shop_step": True},
]

SELL_CYCLE_UNIT = [
    {"click_slot": "first_fish_slot"},
    {"wait": 0.2},
    {"click_slot": "sell_all_button"},
    {"wait": 0.8},
    {"click_slot": "sell_confirm_button"},
    {"wait": 0.2},
]

_SELL_SHOP_CLOSE = [
    {"click_slot": "fish_shop_close_button", "shop_step": True},
    {"wait": 0.3, "shop_step": True},
]

_SELL_AT_SHOP = (
    _SELL_SHOP_OPEN + [{"sell_cycle": True, "shop_step": True}] + _SELL_SHOP_CLOSE
)

SELL_ROUTES = {
    "VIP/VIP+": _RESET_AND_ZOOM
    + [
        {"down": "w"},
        {"wait": 3},
        {"up": "w"},
        {"wait": 0.5},
        {"down": "a"},
        {"wait": 2.5},
        {"down": "w"},
        {"wait": 4},
        {"up": "w"},
        {"up": "a"},
        {"wait": 2},
        {"down": "s"},
        {"wait": 0.3},
        {"up": "s"},
        {"wait": 0.3},
        {"down": "space"},
        {"wait": 0.025},
        {"down": "w"},
        {"wait": 0.96},
        {"up": "space"},
        {"wait": 0.5},
        {"up": "w"},
        {"wait": 0.3},
        {"tap": "e", "shop_step": True},
        {"wait": 0.3, "shop_step": True},
    ]
    + _SELL_AT_SHOP
    + [
        {"down": "a"},
        {"wait": 1.12},
        {"up": "a"},
        {"wait": 0.075},
        {"down": "w"},
        {"wait": 2.35},
        {"up": "w"},
    ],
    "No VIP": _RESET_AND_ZOOM
    + [
        {"down": "w"},
        {"wait": 3.628},
        {"up": "w"},
        {"wait": 0.815},
        {"down": "a"},
        {"wait": 2.035},
        {"down": "w"},
        {"wait": 4.431},
        {"up": "a"},
        {"wait": 0.256},
        {"down": "a"},
        {"wait": 0.176},
        {"up": "a"},
        {"wait": 0.1},
        {"down": "a"},
        {"wait": 0.153},
        {"up": "a"},
        {"wait": 0.064},
        {"down": "a"},
        {"wait": 0.122},
        {"up": "a"},
        {"wait": 0.063},
        {"down": "a"},
        {"wait": 0.245},
        {"up": "a"},
        {"wait": 0.058},
        {"up": "w"},
        {"wait": 0.882},
        {"down": "s"},
        {"wait": 0.18},
        {"up": "s"},
        {"wait": 0.969},
        {"down": "w"},
        {"down": "space"},
        {"wait": 1.236},
        {"up": "space"},
        {"wait": 0.472},
        {"up": "w"},



        {"tap": "e", "shop_step": True},
        {"wait": 0.3, "shop_step": True},
    ]
    + _SELL_AT_SHOP
    + [
        {"down": "a"},
        {"wait": 1.372},
        {"up": "a"},
        {"wait": 0.839},
        {"down": "w"},
        {"wait": 3.137},
        {"up": "w"},
    ],
}


def slot_keys():
    return [key for key, _label in PIXEL_SLOTS]


def region_keys():
    return [key for key, _label in REGION_SLOTS]


def region_label(key):
    for k, label in REGION_SLOTS:
        if k == key:
            return label
    return key


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
    for key in region_keys():
        box = data.get(key)
        if isinstance(box, (list, tuple)) and len(box) == 4:
            out[key] = [int(v) for v in box]
    return out


def route_names():
    return list(SELL_ROUTES.keys())


def get_route(name):
    steps = SELL_ROUTES.get(name)
    if not isinstance(steps, list):
        return None
    return steps
