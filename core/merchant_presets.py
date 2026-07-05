
from . import merchants_data

PRESETS = {
    "[1080p] WINDOWED 1920x1080 (100%)": {
        "general": {
            "dialogue_skip": [1009, 781],
            "merchant_name": [746, 671, 124, 39],
        },
        "shop": {
            "buy_button": [1172, 646],
            "amount_box": [1061, 601],
            "set_max_button": [1344, 602],
            "close_button": [1809, 347],
            "item_slot_1": [864, 677, 189, 55],
            "item_slot_2": [1058, 678, 185, 51],
            "item_slot_3": [1252, 681, 180, 45],
            "item_slot_4": [1441, 679, 185, 53],
            "item_slot_5": [1631, 681, 188, 50],
            "amount_label": [903, 548, 163, 23],
            "item_name": [1110, 360, 480, 34],
        },
        "mari": {
            "open_button": [678, 904],
            "leave_button": [1264, 904],
        },
        "jester": {
            "open_button": [641, 906],
            "exchange_button": [852, 905],
            "leave_button": [1293, 903],
        },
        "rin": {
            "leave_button": [1307, 903],
        },
    },
    "[1080p] FULLSCREEN 1920x1080 (100%)": {
        "general": {
            "dialogue_skip": [1009, 781],
            "merchant_name": [746, 671, 124, 39],
        },
        "shop": {
            "buy_button": [1172, 646],
            "amount_box": [1061, 601],
            "set_max_button": [1344, 602],
            "close_button": [1809, 347],
            "item_slot_1": [864, 677, 189, 55],
            "item_slot_2": [1058, 678, 185, 51],
            "item_slot_3": [1252, 681, 180, 45],
            "item_slot_4": [1441, 679, 185, 53],
            "item_slot_5": [1631, 681, 188, 50],
            "amount_label": [903, 548, 163, 23],
            "item_name": [1110, 360, 480, 34],
        },
        "mari": {
            "open_button": [678, 904],
            "leave_button": [1264, 904],
        },
        "jester": {
            "open_button": [641, 906],
            "exchange_button": [852, 905],
            "leave_button": [1293, 903],
        },
        "rin": {
            "leave_button": [1307, 903],
        },
    },
}

def preset_names():
    return list(PRESETS.keys())

def get_preset(name):
    
    data = PRESETS.get(name)
    if not isinstance(data, dict):
        return None
    out = {}
    for gkey in merchants_data.calib_group_keys():
        gdata = data.get(gkey) or {}
        flat = "pixels" not in gdata and "regions" not in gdata
        src_pixels = gdata if flat else (gdata.get("pixels") or {})
        src_regions = gdata if flat else (gdata.get("regions") or {})
        group_out = {"pixels": {}, "regions": {}}

        for slot in merchants_data.calib_point_keys(gkey):
            pos = src_pixels.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                group_out["pixels"][slot] = [int(pos[0]), int(pos[1])]

        for name_key in merchants_data.calib_region_keys(gkey):
            box = src_regions.get(name_key)
            if isinstance(box, (list, tuple)) and len(box) == 4:
                group_out["regions"][name_key] = [int(v) for v in box]

        out[gkey] = group_out
    return out
