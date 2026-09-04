

from . import extra_calibrations as _ec

PRESETS: dict = {
    "[1080p] WINDOWED 1920x1080 (100%)": {
        "eden": {"pixels": {"eden_click": [761, 922]}, "regions": {}},
    },
    "[1080p] FULLSCREEN 1920x1080 (100%)": {
        "eden": {"pixels": {"eden_click": [745, 969]}, "regions": {}},
    },
    "[WUXGA] WINDOWED 1920x1200 (125%)": {
        "eden": {"pixels": {"eden_click": [718, 1018]}, "regions": {}},
    },
    "[UWQHD] WINDOWED 3440x1440 (150%)": {
        "eden": {"pixels": {"eden_click": [1376, 1185]}, "regions": {}},
    },
}

def preset_names():
    return list(PRESETS.keys())

def get_preset(name):
    
    data = PRESETS.get(name)
    if not isinstance(data, dict):
        return None
    out = {}
    for g in _ec.groups():
        gkey = g["key"]
        gdata = data.get(gkey) or {}
        group_out = {"pixels": {}, "regions": {}}
        src_px = gdata.get("pixels") or {}
        for slot in _ec.point_keys(gkey):
            pos = src_px.get(slot)
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                group_out["pixels"][slot] = [int(pos[0]), int(pos[1])]
        src_rgn = gdata.get("regions") or {}
        for nm in _ec.region_keys(gkey):
            box = src_rgn.get(nm)
            if isinstance(box, (list, tuple)) and len(box) == 4:
                group_out["regions"][nm] = [int(v) for v in box]
        out[gkey] = group_out
    return out
