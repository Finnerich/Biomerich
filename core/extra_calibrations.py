

EXTRA_CALIB_GROUPS = [
    {
        "key": "eden",
        "label": "Eden Calibrations",
        "icon": "fa-solid fa-circle-dot",
        "color": "#111827",
        "points": [
            ("eden_click", "Eden Click Point"),
        ],
        "regions": [],
        "subgroups": [],
    },
]

def groups():
    return EXTRA_CALIB_GROUPS

def group(key):
    for g in EXTRA_CALIB_GROUPS:
        if g["key"] == key:
            return g
    return None

def group_keys():
    return [g["key"] for g in EXTRA_CALIB_GROUPS]

def _all_points(g):
    
    pts = [k for k, _ in g.get("points", [])]
    for sg in g.get("subgroups", []):
        pts += [k for k, _ in sg.get("points", [])]
    return pts

def _all_regions(g):
    
    rgns = [k for k, _ in g.get("regions", [])]
    for sg in g.get("subgroups", []):
        rgns += [k for k, _ in sg.get("regions", [])]
    return rgns

def point_keys(gkey):
    g = group(gkey)
    return _all_points(g) if g else []

def region_keys(gkey):
    g = group(gkey)
    return _all_regions(g) if g else []
